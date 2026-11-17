"""Disposable-schema migration coverage for the notification center."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.schema import CreateSchema, DropSchema

from app.database import get_engine


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_POSTGRES_TESTS") != "1",
        reason="Set RUN_POSTGRES_TESTS=1 for an isolated PostgreSQL schema",
    ),
]


def test_notification_migration_upgrade_and_downgrade_round_trip():
    schema = f"dmi_notifications_{uuid4().hex}"
    with get_engine().begin() as connection:
        connection.execute(CreateSchema(schema))
        try:
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "0026")
            command.upgrade(config, "0027")
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0027"
            assert connection.execute(text("SELECT to_regclass('notifications')")).scalar() == "notifications"
            assert connection.execute(
                text(
                    "SELECT count(*) FROM pg_constraint AS con "
                    "JOIN pg_namespace AS ns ON ns.oid = con.connamespace "
                    "WHERE con.conname = 'uq_notifications_recipient_dedupe' "
                    "AND ns.nspname = current_schema()"
                )
            ).scalar() == 1
            command.downgrade(config, "0026")
            assert connection.execute(text("SELECT to_regclass('notifications')")).scalar() is None
            command.upgrade(config, "0027")
        finally:
            connection.execute(text("SET LOCAL search_path TO public"))
            connection.execute(DropSchema(schema, cascade=True))
