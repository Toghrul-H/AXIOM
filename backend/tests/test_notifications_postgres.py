"""Disposable-schema migration coverage for the notification center."""

import os
from threading import Barrier, Thread
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.auth_models import User
from app.database import get_engine
from app.notification_models import Notification
from app.services.notifications import (
    create_notification,
    create_notifications,
    list_notifications,
)


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
            connection.execute(
                text(
                    "INSERT INTO users (email, password_hash) "
                    "VALUES ('pre-notification@example.test', 'x')"
                )
            )
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
            assert connection.execute(
                text(
                    "SELECT count(*) FROM users "
                    "WHERE email = 'pre-notification@example.test'"
                )
            ).scalar() == 1
            command.downgrade(config, "0026")
            assert connection.execute(text("SELECT to_regclass('notifications')")).scalar() is None
            command.upgrade(config, "0027")
        finally:
            connection.execute(text("SET LOCAL search_path TO public"))
            connection.execute(DropSchema(schema, cascade=True))


def _schema_session(schema: str):
    connection = get_engine().connect()
    connection.execute(text(f'SET search_path TO "{schema}"'))
    connection.commit()
    return connection, Session(connection)


def _close_schema_session(connection, session) -> None:
    session.close()
    connection.execute(text("SET search_path TO public"))
    connection.commit()
    connection.close()


def test_notification_postgresql_concurrency_fanout_isolation_and_rollback():
    schema = f"dmi_notification_race_{uuid4().hex}"
    with get_engine().begin() as connection:
        connection.execute(CreateSchema(schema))
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.upgrade(config, "0027")

    connection, session = _schema_session(schema)
    try:
        recipients = [
            User(email=f"notification-{index}@example.test", password_hash="x")
            for index in range(3)
        ]
        session.add_all(recipients)
        session.commit()
        recipient_ids = [user.id for user in recipients]
    finally:
        _close_schema_session(connection, session)

    barrier = Barrier(2)
    outcomes: list[bool] = []
    failures: list[Exception] = []

    def create_same_notification() -> None:
        worker_connection, worker_session = _schema_session(schema)
        try:
            barrier.wait(timeout=5)
            _, created = create_notification(
                worker_session,
                recipient_user_id=recipient_ids[0],
                kind="QUIZ_AVAILABLE",
                dedupe_key="quiz:77:active",
                payload={"title": "Quiz available", "resource_id": 77},
                link="/student/quizzes",
            )
            worker_session.commit()
            outcomes.append(created)
        except Exception as error:  # Surface worker errors in the assertion below.
            worker_session.rollback()
            failures.append(error)
        finally:
            _close_schema_session(worker_connection, worker_session)

    workers = [Thread(target=create_same_notification) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)
    assert not failures
    assert sorted(outcomes) == [False, True]

    connection, session = _schema_session(schema)
    try:
        assert session.scalar(
            select(Notification).where(
                Notification.recipient_user_id == recipient_ids[0],
                Notification.dedupe_key == "quiz:77:active",
            )
        )
        fanout = create_notifications(
            session,
            recipient_user_ids=recipient_ids,
            kind="COURSE_LESSON_PUBLISHED",
            dedupe_key="lesson:88:published",
            payload={"title": "New course lesson", "resource_id": 88},
            link="/student/course?lesson=88",
        )
        session.commit()
        assert [item.recipient_user_id for item, _ in fanout] == recipient_ids
        recipient_one, _ = list_notifications(
            session, recipient_ids[0], limit=20, cursor=None
        )
        assert {item.recipient_user_id for item in recipient_one} == {recipient_ids[0]}

        create_notification(
            session,
            recipient_user_id=recipient_ids[1],
            kind="QUIZ_AVAILABLE",
            dedupe_key="quiz:rollback:active",
            payload={"title": "Quiz available", "resource_id": 99},
            link="/student/quizzes",
        )
        session.rollback()
        assert session.scalar(
            select(Notification.id).where(
                Notification.dedupe_key == "quiz:rollback:active"
            )
        ) is None
    finally:
        _close_schema_session(connection, session)
        with get_engine().begin() as cleanup:
            cleanup.execute(DropSchema(schema, cascade=True))
