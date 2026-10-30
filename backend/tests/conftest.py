import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL, make_url

BACKEND = Path(__file__).resolve().parents[1]
TEST_URL = os.environ.get("SAFETRADE_TEST_DATABASE_URL")

requires_db = pytest.mark.skipif(TEST_URL is None, reason="SAFETRADE_TEST_DATABASE_URL non défini")


def database_url_for_tests(suffix: str = "") -> URL:
    """Adresse d'une base de test ; le nom finit toujours par « _test »."""
    assert TEST_URL is not None
    url = make_url(TEST_URL)
    assert url.database and url.database.endswith("_test"), "la base de test doit finir par _test"
    return url.set(database=url.database.removesuffix("_test") + suffix + "_test")


def recreate_database(url: URL) -> Engine:
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()
    return create_engine(url)


def alembic_config(engine: Engine) -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    cfg.attributes["database_url"] = engine.url.render_as_string(hide_password=False)
    return cfg


@pytest.fixture(scope="session")
def migrated_engine() -> Iterator[Engine]:
    """Base dédiée aux tests applicatifs, migrée une fois pour la session."""
    engine = recreate_database(database_url_for_tests("_app"))
    command.upgrade(alembic_config(engine), "head")
    yield engine
    engine.dispose()
