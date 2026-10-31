"""
Connexion WebSocket Deriv : appariement par `req_id`, ping, reconnexion, abonnements repris.

Un OTP n'est valable qu'une fois : chaque reconnexion passe par `url_provider`, et donc par
le quota REST de l'adresse IP. C'est ce quota commun qui étale les reconnexions massives.
Aucune requête n'est renvoyée automatiquement ; seuls les abonnements sont rétablis.
"""

import asyncio
import contextlib
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

from app.broker.base import (
    AccountKind,
    ApiRejectedError,
    ConnectionLostError,
    Message,
    MessageHandler,
    OrderOutcomeUnknownError,
    Purchase,
    RateLimitedError,
    RealAccountDisabledError,
    RequestTimeoutError,
)
from app.broker.quotas import Backoff, Quota, QuotaManager, priority_for, quota_for

logger = logging.getLogger("safetrade.deriv")

PUBLIC_WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public"
PING_SECONDS = 30.0
REQUEST_TIMEOUT = 15.0
# Une connexion stable pendant cette durée remet l'attente exponentielle à zéro.
STABLE_SECONDS = 60.0

UrlProvider = Callable[[], Awaitable[str]]


def ensure_account_allowed(kind: AccountKind, real_account_enabled: bool) -> None:
    if kind is AccountKind.REAL and not real_account_enabled:
        raise RealAccountDisabledError("compte réel désactivé")


class _Stream:
    def __init__(
        self, conn: "DerivConnection", call: str, payload: Message, handler: MessageHandler
    ):
        self.conn = conn
        self.call = call
        self.payload = payload
        self.handler = handler
        self.req_id = 0
        self.subscription_id: str | None = None

    async def cancel(self) -> None:
        await self.conn._forget(self)


class DerivConnection:
    """Une connexion par compte. `scope` identifie le compte pour les quotas WebSocket."""

    def __init__(
        self,
        url_provider: UrlProvider,
        quotas: QuotaManager,
        *,
        scope: str,
        ping_seconds: float = PING_SECONDS,
        request_timeout: float = REQUEST_TIMEOUT,
        backoff: Backoff | None = None,
        uses_otp: bool = True,
    ) -> None:
        self._url_provider = url_provider
        self._quotas = quotas
        self._scope = scope
        self._ping_seconds = ping_seconds
        self._request_timeout = request_timeout
        self._backoff = backoff or Backoff()
        self._ws: ClientConnection | None = None
        self._connected = asyncio.Event()
        self._pending: dict[int, asyncio.Future[Message]] = {}
        self._streams: dict[int, _Stream] = {}
        self._next_id = 0
        # Achats dont l'envoi a commencé : leur issue n'est plus certaine après une coupure.
        self._sent: set[int] = set()
        self._task: asyncio.Task[None] | None = None
        self._stopping = False
        self._uses_otp = uses_otp
        self._ever_connected = False
        self._last_received = 0.0
        self.reconnections = 0

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    async def start(self) -> None:
        self._stopping = False
        self._task = asyncio.create_task(self._run(), name=f"deriv:{self._scope}")

    async def stop(self) -> None:
        self._stopping = True
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._fail_pending()

    async def wait_connected(self, timeout: float = 10.0) -> None:
        await asyncio.wait_for(self._connected.wait(), timeout)

    async def _run(self) -> None:
        while not self._stopping:
            opened_at: float | None = None
            try:
                # Quota commun à tous les bots : borne les reconnexions du serveur entier.
                if self._uses_otp:
                    await self._quotas.wait(Quota.REST_IP, "server")
                    await self._quotas.wait(Quota.REST_USER, self._scope)
                url = await self._url_provider()
                async with connect(url, ping_interval=None) as ws:
                    opened_at = time.monotonic()
                    await self._serve(ws)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # toute panne réseau mène à la reconnexion
                logger.warning("connexion Deriv %s perdue : %s", self._scope, type(exc).__name__)
            finally:
                self._ws = None
                self._connected.clear()
                self._fail_pending()
            if opened_at is not None and time.monotonic() - opened_at >= STABLE_SECONDS:
                self._backoff.reset()
            if not self._stopping:
                await asyncio.sleep(self._backoff.next_delay())

    async def _serve(self, ws: ClientConnection) -> None:
        self._ws = ws
        self._last_received = time.monotonic()
        self._connected.set()
        if self._ever_connected:
            self.reconnections += 1
        self._ever_connected = True
        pinger = asyncio.create_task(self._ping_loop(ws))
        reader = asyncio.create_task(self._read_loop(ws))
        try:
            for stream in list(self._streams.values()):
                await self._open_stream(stream)
            await reader
        finally:
            pinger.cancel()
            reader.cancel()

    async def _ping_loop(self, ws: ClientConnection) -> None:
        while True:
            await asyncio.sleep(self._ping_seconds)
            # Connexion muette : le serveur ne répond plus sans avoir fermé.
            if time.monotonic() - self._last_received > 3 * self._ping_seconds:
                await ws.close()
                return
            await ws.send(json.dumps({"ping": 1}))

    async def _read_loop(self, ws: ClientConnection) -> None:
        with contextlib.suppress(ConnectionClosed):
            async for raw in ws:
                self._last_received = time.monotonic()
                await self._dispatch(json.loads(raw))

    async def _dispatch(self, message: Message) -> None:
        req_id = message.get("req_id")
        if not isinstance(req_id, int):
            return
        future = self._pending.pop(req_id, None)
        if future is not None and not future.done():
            future.set_result(message)
        stream = self._streams.get(req_id)
        if stream is not None:
            if "subscription" in message:
                stream.subscription_id = message["subscription"].get("id")
            if "error" in message:
                logger.warning(
                    "abonnement %s refusé : %s", stream.call, message["error"].get("code")
                )
                return
            try:
                await stream.handler(message)
            except Exception:
                # Une erreur de traitement ne doit pas couper la connexion ni les autres flux.
                logger.exception("erreur dans le traitement du flux %s", stream.call)

    def _fail_pending(self) -> None:
        for future in self._pending.values():
            if not future.done():
                future.set_exception(ConnectionLostError())
        self._pending.clear()

    def _allocate_id(self) -> int:
        self._next_id += 1
        return self._next_id

    async def _send(self, call: str, payload: Message, req_id: int) -> asyncio.Future[Message]:
        quota = quota_for(call)
        if quota is not None:
            await self._quotas.wait(quota, self._scope, priority_for(call))
        ws = self._ws
        if ws is None:
            raise ConnectionLostError
        future: asyncio.Future[Message] = asyncio.get_running_loop().create_future()
        self._pending[req_id] = future
        if call == "buy":
            self._sent.add(req_id)
        await ws.send(json.dumps({**payload, "req_id": req_id}))
        return future

    async def _exchange(self, call: str, payload: Message) -> Message:
        req_id = self._allocate_id()
        try:
            future = await self._send(call, payload, req_id)
        except ConnectionClosed as exc:
            self._pending.pop(req_id, None)
            raise ConnectionLostError(call) from exc
        return await self._await_response(call, future, req_id)

    async def _await_response(
        self, call: str, future: asyncio.Future[Message], req_id: int
    ) -> Message:
        try:
            response = await asyncio.wait_for(future, self._request_timeout)
        except TimeoutError as exc:
            self._pending.pop(req_id, None)
            raise RequestTimeoutError(call) from exc
        return self._checked(response)

    @staticmethod
    def _checked(response: Message) -> Message:
        error: Any = response.get("error")
        if error:
            code = str(error.get("code", "unknown"))
            kind = RateLimitedError if code == "RateLimit" else ApiRejectedError
            raise kind(code, str(error.get("message", "")), error.get("details"))
        return response

    async def request(self, call: str, payload: Message) -> Message:
        """Requête unique. Aucune nouvelle tentative : l'appelant décide selon l'opération."""
        return await self._exchange(call, payload)

    async def _open_stream(self, stream: _Stream) -> asyncio.Future[Message]:
        self._streams.pop(stream.req_id, None)
        stream.req_id = self._allocate_id()
        self._streams[stream.req_id] = stream
        future = await self._send(stream.call, {**stream.payload, "subscribe": 1}, stream.req_id)
        # Lors d'une reprise, personne n'attend ce résultat : son erreur est consommée ici.
        future.add_done_callback(lambda f: f.cancelled() or f.exception())
        return future

    async def subscribe(self, call: str, payload: Message, handler: MessageHandler) -> _Stream:
        """Abonnement rétabli après chaque reconnexion, sous un nouvel identifiant."""
        stream = _Stream(self, call, payload, handler)
        try:
            await self._await_response(call, await self._open_stream(stream), stream.req_id)
        except Exception:
            self._streams.pop(stream.req_id, None)
            raise
        return stream

    async def _forget(self, stream: _Stream) -> None:
        self._streams.pop(stream.req_id, None)
        if stream.subscription_id and self.connected:
            await self.request("forget", {"forget": stream.subscription_id})

    async def buy(self, proposal_id: str, max_price: float) -> Purchase:
        """
        Achat par identifiant de proposition uniquement. Aucun achat n'est renvoyé : si la
        réponse manque, `OrderOutcomeUnknownError` impose de consulter `statement` d'abord.
        """
        sent_at = time.time()
        req_id = self._allocate_id()
        payload = {"buy": proposal_id, "price": max_price}
        # Non envoyé : ConnectionLostError, l'ordre n'a jamais quitté SafeTrade.
        try:
            future = await self._send("buy", payload, req_id)
            response = await asyncio.wait_for(future, self._request_timeout)
        except (TimeoutError, ConnectionClosed) as exc:
            self._pending.pop(req_id, None)
            raise OrderOutcomeUnknownError(proposal_id, sent_at) from exc
        except ConnectionLostError as exc:
            if req_id not in self._sent:
                raise
            raise OrderOutcomeUnknownError(proposal_id, sent_at) from exc
        finally:
            self._sent.discard(req_id)
        buy = self._checked(response)["buy"]
        return Purchase(
            contract_id=int(buy["contract_id"]),
            buy_price=float(buy["buy_price"]),
            balance_after=float(buy["balance_after"]),
            transaction_id=int(buy["transaction_id"]),
            shortcode=str(buy["shortcode"]),
        )
