from fastapi import FastAPI
from pydantic import BaseModel

from app.config import get_settings


class Health(BaseModel):
    status: str
    environment: str


def create_app() -> FastAPI:
    settings = get_settings()
    # Documentation interactive désactivée hors développement.
    is_dev = settings.environment == "development"
    app = FastAPI(
        title="SafeTrade API",
        docs_url="/docs" if is_dev else None,
        redoc_url=None,
        openapi_url="/openapi.json" if is_dev else None,
    )

    @app.get("/health", response_model=Health, tags=["system"])
    def health() -> Health:
        return Health(status="ok", environment=settings.environment)

    return app


app = create_app()
