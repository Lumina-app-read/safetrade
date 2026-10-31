"""
Processus moteur : `python -m app.trading.worker`. Seul ce processus émet des ordres.

Chaque session active est prise sous un bail par compte, relu juste avant chaque achat. Deux
moteurs peuvent donc tourner, par exemple pendant un déploiement, sans jamais agir à deux.
"""

import asyncio
import logging
import signal
import socket
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.auth.mailer import build_mailer
from app.billing.gateway import build_gateways
from app.billing.notices import remind_expiring
from app.billing.router import reconcile
from app.broker.base import AccountKind, RealAccountDisabledError
from app.broker.deriv import DerivConnection, ensure_account_allowed
from app.broker.deriv_rest import DerivAccount, DerivRest
from app.broker.deriv_trading import DerivTrading
from app.broker.quotas import QuotaManager, RedisQuotaStore
from app.config import Settings, get_settings
from app.db.models import BotSession, BotState, DerivConnectionRecord
from app.db.session import get_engine
from app.deriv import service
from app.logs import configure_json_logs
from app.market.lease import LeadershipLostError, Lease, lead_while_holding
from app.market.store import RedisMarketStore
from app.market.worker import signal_presence
from app.trading.bot import BotRunner
from app.trading.execution import Executor, Journal

logger = logging.getLogger("safetrade.trading")

SCAN_SECONDS = 2.0
BILLING_SECONDS = 300.0


def can_trade(settings: Settings) -> bool:
    """
    Sans identifiant Deriv, aucun bot ne peut tourner. Une installation neuve doit tout de même
    démarrer en développement ; hors développement, le moteur refuse, comme l'API (app/main.py).
    """
    if settings.deriv_app_id:
        return True
    if settings.environment not in ("development", "test"):
        raise RuntimeError("SAFETRADE_DERIV_APP_ID est obligatoire pour le moteur.")
    logger.warning("moteur sans identifiant Deriv", extra={"event": "trading.no_app_id"})
    return False


class Engine:
    def __init__(self, settings: Settings, client: Redis) -> None:
        self._can_trade = can_trade(settings)
        self._settings = settings
        self._client = client
        self._owner = f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
        self._factory = sessionmaker(get_engine(), expire_on_commit=False)
        self._journal = Journal(self._factory)
        self._quotas = QuotaManager(RedisQuotaStore(client))
        self._rest = DerivRest(
            settings.deriv_app_id or "",
            self._quotas,
            real_account_enabled=settings.real_account_enabled,
        )
        self._market = RedisMarketStore(client)
        self._running: dict[uuid.UUID, asyncio.Task[None]] = {}

    async def scan(self) -> None:
        if not self._can_trade:
            return

        def active(db: Any) -> list[BotSession]:
            return list(db.scalars(select(BotSession).where(BotSession.ended_at.is_(None))))

        for session in await self._journal.run(active):
            task = self._running.get(session.id)
            if task is None or task.done():
                self._running[session.id] = asyncio.create_task(self._hold(session))

    async def _hold(self, session: BotSession) -> None:
        lease = Lease(self._client, self._owner, key=f"bot:{session.account_id}")
        try:
            if await lease.acquire():
                await lead_while_holding(lease, lambda: self._run(session, lease))
        except (LeadershipLostError, RedisError) as exc:
            logger.warning(
                "session interrompue",
                extra={"event": "trading.session_stopped", "reason": type(exc).__name__},
            )

    def _connection(self, session: BotSession) -> DerivConnection:
        kind = AccountKind(session.account_kind)
        ensure_account_allowed(kind, self._settings.real_account_enabled)

        def record(db: Any) -> DerivConnectionRecord:
            row = db.scalars(
                select(DerivConnectionRecord).where(
                    DerivConnectionRecord.user_id == session.user_id
                )
            ).one()
            return row  # type: ignore[no-any-return]

        account = DerivAccount(session.account_id, kind, "USD", "0", "active")

        async def url() -> str:
            stored = await self._journal.run(record)
            token = service.read_token(self._settings, stored)
            return await self._rest.otp_url(token, account, session.account_id)

        return DerivConnection(url, self._quotas, scope=session.account_id)

    async def _run(self, session: BotSession, lease: Lease) -> None:
        try:
            connection = self._connection(session)
        except RealAccountDisabledError:

            def refuse(db: Any) -> None:
                row = db.get_one(BotSession, session.id)
                row.state = BotState.ERROR
                row.error_code = "deriv.real_disabled"

            await self._journal.run(refuse)
            return
        trading = DerivTrading(connection)
        executor = Executor(self._journal, trading, lease.renew)
        runner = BotRunner(
            session.id,
            self._journal,
            trading,
            executor,
            self._market,
            real_enabled=self._settings.real_account_enabled,
        )
        await connection.start()
        try:
            await runner.run()
        finally:
            await connection.stop()

    async def billing(self) -> None:
        """Rapprochement des paiements et rappels d'échéance, à côté des sessions."""
        mailer = build_mailer(self._settings)
        gateways = build_gateways(self._settings)
        while True:
            await asyncio.sleep(BILLING_SECONDS)
            now = datetime.now(UTC)
            try:
                for gateway in gateways.values():
                    if mailer is not None:
                        await reconcile(self._factory, gateway, mailer, self._settings, now)
                if mailer is not None:
                    await asyncio.to_thread(
                        remind_expiring, self._factory, mailer, self._settings, now
                    )
            except SQLAlchemyError:
                logger.exception("tâche d'abonnement", extra={"event": "billing.task_failed"})

    async def stop(self) -> None:
        for task in self._running.values():
            task.cancel()
        await asyncio.gather(*self._running.values(), return_exceptions=True)

    async def run(self) -> None:
        role: dict[str, Any] = {"owner": self._owner, "role": "engine", "since": time.time()}
        presence = asyncio.create_task(signal_presence(self._client, role))
        billing = asyncio.create_task(self.billing())
        try:
            while True:
                await self.scan()
                await asyncio.sleep(SCAN_SECONDS)
        finally:
            presence.cancel()
            billing.cancel()
            await self.stop()


async def main() -> None:
    settings = get_settings()
    if settings.redis_url is None or settings.database_url is None:
        raise RuntimeError("Base de données et Redis sont obligatoires pour le moteur.")
    client = Redis.from_url(settings.redis_url.get_secret_value())
    work = asyncio.create_task(Engine(settings, client).run())
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, work.cancel)
    try:
        await work
    except asyncio.CancelledError:
        # Les positions ouvertes restent protégées par leur stop loss chez Deriv.
        logger.info("moteur arrêté", extra={"event": "trading.engine_stopped"})


if __name__ == "__main__":
    configure_json_logs()
    asyncio.run(main())
