"""Migrations sur une vraie base PostgreSQL (base de test dédiée, jamais celle de développement)."""

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.db.base import Base

TEST_URL = os.environ.get("SAFETRADE_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(TEST_URL is None, reason="SAFETRADE_TEST_DATABASE_URL non défini")

BACKEND = Path(__file__).resolve().parents[1]
TABLES = {"users", "sessions", "audit_log"}


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    assert TEST_URL is not None
    url = make_url(TEST_URL)
    assert url.database and url.database.endswith("_test"), "la base de test doit finir par _test"
    # Base de test recréée à neuf à chaque exécution.
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()
    eng = create_engine(url)
    yield eng
    eng.dispose()


@pytest.fixture(scope="module")
def alembic_config(engine: Engine) -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    cfg.attributes["database_url"] = engine.url.render_as_string(hide_password=False)
    return cfg


def tables(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def test_upgrade_downgrade_upgrade(engine: Engine, alembic_config: Config) -> None:
    command.upgrade(alembic_config, "head")
    assert tables(engine) == TABLES

    command.downgrade(alembic_config, "base")
    assert tables(engine) == set()
    with engine.connect() as conn:
        leftovers = conn.execute(
            text(
                "SELECT typname FROM pg_type WHERE typname IN ('user_role', 'user_status') "
                "UNION ALL SELECT proname FROM pg_proc WHERE proname = 'audit_log_immutable'"
            )
        ).all()
    assert leftovers == []

    command.upgrade(alembic_config, "head")
    assert tables(engine) == TABLES


def test_models_match_migrations(engine: Engine, alembic_config: Config) -> None:
    command.upgrade(alembic_config, "head")
    with engine.connect() as conn:
        diff = compare_metadata(
            MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata
        )
    assert diff == []


def test_audit_log_is_append_only(engine: Engine, alembic_config: Config) -> None:
    command.upgrade(alembic_config, "head")
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO audit_log (action, result) VALUES ('test.append', 'success')")
        )

    for statement in (
        "UPDATE audit_log SET result = 'failure'",
        "DELETE FROM audit_log",
        "TRUNCATE audit_log",
    ):
        with pytest.raises(DBAPIError, match="ajout seul"), engine.begin() as conn:
            conn.execute(text(statement))

    with engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM audit_log WHERE result = 'success'")
            ).scalar_one()
            >= 1
        )


def test_email_unique_case_insensitive(engine: Engine, alembic_config: Config) -> None:
    command.upgrade(alembic_config, "head")
    insert = text(
        "INSERT INTO users (id, email, password_hash, first_name) VALUES (:id, :email, 'x', 'Test')"
    )
    with engine.begin() as conn:
        conn.execute(insert, {"id": uuid.uuid4(), "email": "Clovis@Example.com"})
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(insert, {"id": uuid.uuid4(), "email": "clovis@example.com"})
