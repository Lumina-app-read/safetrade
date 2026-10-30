"""Erreurs de l'API : un code stable que le front-end traduit, jamais un texte en dur."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status: int, code: str, headers: dict[str, str] | None = None) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.headers = headers


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    def api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse({"error": exc.code}, status_code=exc.status, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Champs fautifs seulement : jamais les valeurs saisies (mot de passe...).
        fields = sorted({".".join(str(p) for p in e["loc"][1:]) for e in exc.errors()})
        return JSONResponse({"error": "validation.invalid", "fields": fields}, status_code=422)
