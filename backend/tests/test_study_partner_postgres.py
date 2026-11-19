"""PostgreSQL-only isolation and concurrency coverage for Study Partner."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.auth_models import User
from app.course_models import CourseChapter
from app.database import get_engine
from app.models import Topic
from app.routers.study_partner import accept_request, create_block, create_request, decline_request, put_my_profile
from app.study_partner_models import StudyPartnerRequest
from app.study_partner_schemas import StudyPartnerBlockCreate, StudyPartnerProfileWrite, StudyPartnerRequestCreate
from app.services.password_reset import _claim_outbox, issue_password_reset, reset_password
from app.auth_models import PasswordResetOutbox, PasswordResetToken


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Set RUN_POSTGRES_TESTS=1 for an isolated PostgreSQL schema"),
]


def profile(name: str, topic_id: int) -> StudyPartnerProfileWrite:
    return StudyPartnerProfileWrite(
        display_name=name,
        is_participating=True,
        is_discoverable=True,
        study_format="EITHER",
        topics=[{"topic_id": topic_id, "purpose": "WANT_TO_STUDY"}],
        availability=[{"weekday": 1, "start_minute": 600, "end_minute": 720}],
    )


@pytest.fixture
def study_partner_schema():
    """Create/drop a unique schema; public and development tables are untouched."""
    schema = f"dmi_study_partner_{uuid4().hex}"
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
        try:
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            config.attributes["connection"] = connection
            config.attributes["version_table_schema"] = schema
            command.upgrade(config, "head")
        except Exception:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            raise
    try:
        yield schema
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        # search_path is a connection-level setting; discard pooled connections
        # configured for the disposable schema before unrelated tests run.
        engine.dispose()


def schema_session(schema: str) -> tuple[Session, object]:
    connection = get_engine().connect()
    connection.execute(text(f'SET search_path TO "{schema}"'))
    connection.commit()
    return Session(connection), connection


def seed(schema: str) -> tuple[int, int, int]:
    session, connection = schema_session(schema)
    try:
        topic = session.scalar(select(Topic).where(Topic.slug == "logic"))
        assert topic is not None
        first = User(email="study-a@example.test", password_hash="x", role="STUDENT", email_verified=True)
        second = User(email="study-b@example.test", password_hash="x", role="STUDENT", email_verified=True)
        session.add_all((first, second))
        session.flush()
        put_my_profile(profile("Ada", topic.id), session, first)
        put_my_profile(profile("Bela", topic.id), session, second)
        return first.id, second.id, topic.id
    finally:
        session.close()
        connection.close()


def test_postgres_reciprocal_concurrency_creates_one_pending_request(study_partner_schema):
    first_id, second_id, _ = seed(study_partner_schema)
    barrier = Barrier(2)

    def send(actor_id: int, recipient_id: int):
        session, connection = schema_session(study_partner_schema)
        try:
            actor = session.get(User, actor_id)
            assert actor is not None
            barrier.wait(timeout=10)
            try:
                return "created", create_request(StudyPartnerRequestCreate(recipient_profile_id=recipient_id), session, actor)["status"]
            except HTTPException as error:
                return "error", error.status_code
        finally:
            session.close()
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda pair: send(*pair), ((first_id, second_id), (second_id, first_id))))
    assert sorted(outcomes) == [("created", "PENDING"), ("error", 409)]

    session, connection = schema_session(study_partner_schema)
    try:
        assert session.scalar(select(func.count(StudyPartnerRequest.id)).where(StudyPartnerRequest.status == "PENDING")) == 1
    finally:
        session.close()
        connection.close()


def test_postgres_course_migration_is_present(study_partner_schema):
    session, connection = schema_session(study_partner_schema)
    try:
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        config.attributes["version_table_schema"] = study_partner_schema
        command.downgrade(config, "0023")
        assert connection.execute(text("SELECT to_regclass('course_chapters')")).scalar() is None
        command.upgrade(config, "0024")
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0024"
        chapter = CourseChapter(title="Sets", slug="sets", position=0)
        session.add(chapter)
        session.flush()
        chapter_id = chapter.id
        session.commit()
        assert chapter_id is not None
    finally:
        session.close()
        connection.close()


def test_postgres_password_reset_migration_round_trip_and_concurrent_consumption(study_partner_schema):
    session, connection = schema_session(study_partner_schema)
    try:
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        config.attributes["version_table_schema"] = study_partner_schema
        command.downgrade(config, "0026")
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0026"
        assert connection.execute(text("SELECT to_regclass('password_reset_tokens')")).scalar() == "password_reset_tokens"
        assert connection.execute(text("SELECT to_regclass('password_reset_outbox')")).scalar() == "password_reset_outbox"
        command.downgrade(config, "0025")
        assert connection.execute(text("SELECT to_regclass('password_reset_outbox')")).scalar() is None
        command.downgrade(config, "0024")
        assert connection.execute(text("SELECT to_regclass('password_reset_tokens')")).scalar() is None
        command.upgrade(config, "0026")
        connection.execute(text(f'SET search_path TO "{study_partner_schema}"'))
        connection.commit()
        user = User(email="reset-race@example.test", password_hash="old", role="STUDENT", email_verified=True)
        session.add(user)
        session.commit()
        cipher = Fernet(Fernet.generate_key())
        issue_password_reset(session, user, cipher)
        session.commit()
        assert session.get(PasswordResetToken, user.id) is not None
        outbox = session.scalar(
            select(PasswordResetOutbox).where(PasswordResetOutbox.user_id == user.id)
        )
        assert outbox is not None
        user_id = user.id
        token = cipher.decrypt(outbox.token_ciphertext.encode("ascii")).decode("ascii")
    finally:
        session.close()
        connection.close()

    barrier = Barrier(2)
    def consume():
        worker, worker_connection = schema_session(study_partner_schema)
        try:
            barrier.wait(timeout=10)
            try:
                reset_password(worker, token, "new-password-42!")
                return "consumed"
            except HTTPException as error:
                return "error", error.status_code
        finally:
            worker.close()
            worker_connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: consume(), range(2)))
    assert sorted(outcomes, key=str) == [("error", 400), "consumed"]
    session, connection = schema_session(study_partner_schema)
    try:
        assert session.get(PasswordResetToken, user_id) is None
    finally:
        session.close()
        connection.close()


def test_postgres_reset_outbox_claims_work_once_across_workers(study_partner_schema):
    session, connection = schema_session(study_partner_schema)
    try:
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        config.attributes["version_table_schema"] = study_partner_schema
        command.downgrade(config, "0026")
        user = User(email="outbox-race@example.test", password_hash="old", role="STUDENT", email_verified=True)
        session.add(user)
        session.commit()
        issue_password_reset(session, user, Fernet(Fernet.generate_key()))
        session.commit()
    finally:
        session.close()
        connection.close()

    barrier = Barrier(2)
    def claim_once():
        worker, worker_connection = schema_session(study_partner_schema)
        try:
            barrier.wait(timeout=10)
            return len(_claim_outbox(worker, datetime.now(timezone.utc), 1))
        finally:
            worker.close()
            worker_connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        claimed = list(pool.map(lambda _: claim_once(), range(2)))
    assert sorted(claimed) == [0, 1]


def test_postgres_transition_and_block_races_remain_controlled(study_partner_schema):
    first_id, second_id, topic_id = seed(study_partner_schema)
    session, connection = schema_session(study_partner_schema)
    try:
        first = session.get(User, first_id)
        assert first is not None
        request_id = create_request(StudyPartnerRequestCreate(recipient_profile_id=second_id), session, first)["id"]
    finally:
        session.close()
        connection.close()

    barrier = Barrier(2)

    def transition(action):
        session, connection = schema_session(study_partner_schema)
        try:
            actor = session.get(User, second_id)
            assert actor is not None
            barrier.wait(timeout=10)
            try:
                result = (accept_request if action == "accept" else decline_request)(request_id, session, actor)
                return "updated", result["status"]
            except HTTPException as error:
                return "error", error.status_code
        finally:
            session.close()
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(transition, ("accept", "decline")))
    assert sorted(outcomes)[0] == ("error", 409)
    assert sorted(outcomes)[1] in (("updated", "ACCEPTED"), ("updated", "DECLINED"))

    session, connection = schema_session(study_partner_schema)
    try:
        first = session.get(User, first_id)
        third = User(email="study-c@example.test", password_hash="x", role="STUDENT", email_verified=True)
        session.add(third)
        session.flush()
        put_my_profile(profile("Csilla", topic_id), session, third)
        assert first is not None
        third_id = third.id
        second_request_id = create_request(StudyPartnerRequestCreate(recipient_profile_id=third_id), session, first)["id"]
    finally:
        session.close()
        connection.close()

    barrier = Barrier(2)

    def accept_or_block(action):
        session, connection = schema_session(study_partner_schema)
        try:
            actor_id = third_id if action == "accept" else first_id
            actor = session.get(User, actor_id)
            assert actor is not None
            barrier.wait(timeout=10)
            try:
                if action == "accept":
                    accept_request(second_request_id, session, actor)
                else:
                    create_block(StudyPartnerBlockCreate(blocked_user_id=third_id), session, actor)
                return "completed"
            except HTTPException as error:
                return error.status_code
        finally:
            session.close()
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(accept_or_block, ("accept", "block")))
    assert "completed" in outcomes
    session, connection = schema_session(study_partner_schema)
    try:
        assert session.get(StudyPartnerRequest, second_request_id).status == "CANCELLED"
    finally:
        session.close()
        connection.close()

    session, connection = schema_session(study_partner_schema)
    try:
        fourth = User(email="study-d@example.test", password_hash="x", role="STUDENT", email_verified=True)
        session.add(fourth)
        session.flush()
        put_my_profile(profile("Dora", topic_id), session, fourth)
        fourth_id = fourth.id
    finally:
        session.close()
        connection.close()

    barrier = Barrier(2)

    def request_or_block(action):
        session, connection = schema_session(study_partner_schema)
        try:
            actor = session.get(User, first_id)
            assert actor is not None
            barrier.wait(timeout=10)
            try:
                if action == "request":
                    create_request(StudyPartnerRequestCreate(recipient_profile_id=fourth_id), session, actor)
                    return "created"
                create_block(StudyPartnerBlockCreate(blocked_user_id=fourth_id), session, actor)
                return "blocked"
            except HTTPException as error:
                return error.status_code
        finally:
            session.close()
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(request_or_block, ("request", "block")))
    assert "blocked" in outcomes
    session, connection = schema_session(study_partner_schema)
    try:
        assert session.scalar(
            select(func.count(StudyPartnerRequest.id)).where(
                StudyPartnerRequest.pair_low_user_id == min(first_id, fourth_id),
                StudyPartnerRequest.pair_high_user_id == max(first_id, fourth_id),
                StudyPartnerRequest.status == "PENDING",
            )
        ) == 0
    finally:
        session.close()
        connection.close()


def test_postgres_0023_downgrade_upgrade_round_trip(study_partner_schema):
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(text(f'SET LOCAL search_path TO "{study_partner_schema}"'))
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        config.attributes["version_table_schema"] = study_partner_schema
        command.downgrade(config, "0022")
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0022"
        assert connection.scalar(text("SELECT to_regclass('study_partner_messages')")) is None
        command.upgrade(config, "0023")
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0023"
        assert connection.scalar(text("SELECT to_regclass('study_partner_messages')")) == "study_partner_messages"
