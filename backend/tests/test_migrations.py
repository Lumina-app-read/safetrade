"""Migrations sur une vraie base PostgreSQL (base de test dédiée, jamais celle de développement)."""

import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.db.base import Base
from tests.conftest import alembic_config as make_config
from tests.conftest import database_url_for_tests, recreate_database, requires_db

pytestmark = requires_db

TABLES = {
    "users",
    "sessions",
    "audit_log",
    "email_verification_tokens",
    "mfa_challenges",
    "recovery_codes",
    "password_reset_tokens",
}


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    # Base propre à ce module : montées et descentes ne gênent pas les autres tests.
    eng = recreate_database(database_url_for_tests())
    yield eng
    eng.dispose()


@pytest.fixture(scope="module")
def alembic_config(engine: Engine) -> Config:
    return make_config(engine)


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
