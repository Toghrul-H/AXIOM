"""Focused isolated coverage for the Study Partner backend."""

from datetime import timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import JSON, MetaData, UniqueConstraint, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.auth import get_current_user, issue_session, student_user
from app.auth_models import User
from app.database import Base
from app.main import app
from app.models import Topic
from app.routers.study_partner import (
    accept_request,
    cancel_request,
    chat_messages,
    chats,
    create_block,
    create_request,
    decline_request,
    get_my_profile,
    partners,
    put_my_profile,
    requests,
    send_chat_message,
)
from app.study_partner_models import StudyPartnerAvailability, StudyPartnerBlock, StudyPartnerRequest, StudyPartnerTopic
from app.study_partner_schemas import StudyPartnerBlockCreate, StudyPartnerMessageCreate, StudyPartnerProfileWrite, StudyPartnerRequestCreate


def setup():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        clone = table.to_metadata(metadata)
        for column in clone.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()
        for constraint in clone.constraints:
            if isinstance(constraint, UniqueConstraint) and constraint.name in {
                "uq_question_options_position",
                "uq_quiz_questions_position",
            }:
                constraint.deferrable = None
                constraint.initially = None
    metadata.create_all(engine)
    session = Session(engine)
    session.execute(text("PRAGMA foreign_keys = ON"))
    topic = Topic(slug="logic", name="Logic", sort_order=1)
    second_topic = Topic(slug="sets", name="Sets", sort_order=2)
    student = User(email="student@example.test", password_hash="x", role="STUDENT", email_verified=True)
    partner = User(email="partner@example.test", password_hash="x", role="STUDENT", email_verified=True)
    third = User(email="third@example.test", password_hash="x", role="STUDENT", email_verified=True)
    fourth = User(email="fourth@example.test", password_hash="x", role="STUDENT", email_verified=True)
    lecturer = User(email="lecturer@example.test", password_hash="x", role="LECTURER", email_verified=True)
    session.add_all((topic, second_topic, student, partner, third, fourth, lecturer))
    session.commit()
    return session, student, partner, third, fourth, lecturer, topic, second_topic


def profile_payload(name: str, topic_id: int, **overrides) -> StudyPartnerProfileWrite:
    payload = {
        "display_name": name,
        "is_participating": True,
        "is_discoverable": True,
        "study_format": "EITHER",
        "introduction": "Happy to study discrete mathematics.",
        "topics": [{"topic_id": topic_id, "purpose": "WANT_TO_STUDY"}],
        "availability": [{"weekday": 1, "start_minute": 600, "end_minute": 720}],
    }
    payload.update(overrides)
    return StudyPartnerProfileWrite.model_validate(payload)


def cookie_request(cookie: str, method: str = "PUT") -> Request:
    return Request({"type": "http", "method": method, "headers": [(b"cookie", cookie.encode())]})


def test_profile_opt_in_validation_student_authorization_and_csrf():
    session, student, _, _, _, lecturer, topic, _ = setup()
    try:
        assert get_my_profile(session, student) == {"exists": False}
        with pytest.raises(HTTPException) as role_error:
            student_user(lecturer)
        assert role_error.value.status_code == 403
        response = Response()
        csrf = issue_session(session, student, response)
        cookie = response.headers["set-cookie"].split(";", 1)[0]
        with pytest.raises(HTTPException) as csrf_error:
            get_current_user(cookie_request(cookie), session, None)
        assert csrf_error.value.status_code == 403
        assert get_current_user(cookie_request(cookie), session, csrf).id == student.id
        created = put_my_profile(profile_payload("Ada", topic.id), session, student)
        assert created["is_discoverable"] is True and created["topics"][0]["name"] == "Logic"
        with pytest.raises(ValueError, match="overlap"):
            profile_payload("Ada", topic.id, availability=[{"weekday": 1, "start_minute": 600, "end_minute": 720}, {"weekday": 1, "start_minute": 700, "end_minute": 800}])
        with pytest.raises(HTTPException) as topic_error:
            put_my_profile(profile_payload("Ada", 99999), session, student)
        assert topic_error.value.status_code == 422
    finally:
        session.close()


def test_profile_payload_rejects_invalid_names_formats_topics_and_availability():
    session, _, _, _, _, _, topic, _ = setup()
    try:
        for invalid in (
            {"display_name": "  "},
            {"display_name": "A\x01da"},
            {"study_format": "HYBRID"},
            {"topics": [{"topic_id": topic.id, "purpose": "WANT_TO_STUDY"}, {"topic_id": topic.id, "purpose": "WANT_TO_STUDY"}]},
            {"availability": [{"weekday": 7, "start_minute": 1, "end_minute": 2}]},
        ):
            with pytest.raises(ValidationError):
                profile_payload("Ada", topic.id, **invalid)
    finally:
        session.close()


def test_authentication_rejects_unverified_inactive_and_non_student_accounts():
    session, student, _, _, _, lecturer, _, _ = setup()
    unverified = User(email="unverified@example.test", password_hash="x", role="STUDENT", email_verified=False)
    inactive = User(email="inactive@example.test", password_hash="x", role="STUDENT", email_verified=True, is_active=False)
    session.add_all((unverified, inactive))
    session.commit()
    try:
        for user in (unverified, inactive):
            response = Response()
            issue_session(session, user, response)
            cookie = response.headers["set-cookie"].split(";", 1)[0]
            with pytest.raises(HTTPException) as error:
                get_current_user(cookie_request(cookie, "GET"), session)
            assert error.value.status_code == 401 and "@" not in error.value.detail
        with pytest.raises(HTTPException) as role_error:
            student_user(lecturer)
        assert role_error.value.status_code == 403
        assert student_user(student).id == student.id
    finally:
        session.close()


def test_study_partner_routes_are_registered():
    paths = set(app.openapi()["paths"])
    assert {
        "/study-partner/me",
        "/study-partner/partners",
        "/study-partner/requests",
        "/study-partner/requests/{request_id}/accept",
        "/study-partner/requests/{request_id}/decline",
        "/study-partner/requests/{request_id}/cancel",
        "/study-partner/blocks",
        "/study-partner/blocks/{user_id}",
        "/study-partner/chats",
        "/study-partner/chats/{request_id}/messages",
    } <= paths


def test_discovery_hides_private_fields_filters_and_blocks():
    session, student, partner, third, _, _, topic, second_topic = setup()
    try:
        put_my_profile(profile_payload("Ada", topic.id), session, student)
        put_my_profile(profile_payload("Bela", topic.id, topics=[{"topic_id": topic.id, "purpose": "CAN_HELP"}]), session, partner)
        put_my_profile(profile_payload("Hidden", second_topic.id, is_discoverable=False), session, third)
        result = partners(session, student, [topic.id], None, 0, 20)
        assert len(result) == 1 and result[0]["display_name"] == "Bela"
        assert "email" not in str(result).lower() and "availability" not in result[0]
        assert result[0]["complementary_topics"][0]["name"] == "Logic"
        create_block(StudyPartnerBlockCreate(blocked_user_id=partner.id), session, student)
        assert partners(session, student, [], None, 0, 20) == []
    finally:
        session.close()


def test_discovery_uses_explainable_stable_ranking_without_exposing_scores():
    session, student, partner, third, fourth, _, topic, second_topic = setup()
    try:
        put_my_profile(
            profile_payload(
                "Ada",
                topic.id,
                study_format="ONLINE",
                topics=[
                    {"topic_id": topic.id, "purpose": "WANT_TO_STUDY"},
                    {"topic_id": second_topic.id, "purpose": "CAN_HELP"},
                ],
            ),
            session,
            student,
        )
        put_my_profile(
            profile_payload(
                "Bela",
                topic.id,
                study_format="ONLINE",
                topics=[{"topic_id": topic.id, "purpose": "WANT_TO_STUDY"}],
            ),
            session,
            partner,
        )
        put_my_profile(
            profile_payload(
                "Csilla",
                topic.id,
                study_format="EITHER",
                topics=[{"topic_id": topic.id, "purpose": "CAN_HELP"}],
            ),
            session,
            third,
        )
        put_my_profile(
            profile_payload(
                "Dora",
                second_topic.id,
                study_format="ONLINE",
                topics=[{"topic_id": second_topic.id, "purpose": "WANT_TO_STUDY"}],
            ),
            session,
            fourth,
        )
        first = partners(session, student, [], None, 0, 20)
        second = partners(session, student, [], None, 0, 20)
        assert [item["profile_id"] for item in first] == [partner.id, fourth.id, third.id]
        assert [item["profile_id"] for item in second] == [item["profile_id"] for item in first]
        assert all("rank" not in item and "email" not in item and "availability" not in item for item in first)
    finally:
        session.close()


def test_request_lifecycle_reciprocal_guard_pause_and_blocking():
    session, student, partner, third, fourth, _, topic, _ = setup()
    try:
        for user, name in ((student, "Ada"), (partner, "Bela"), (third, "Csilla"), (fourth, "Dora")):
            put_my_profile(profile_payload(name, topic.id), session, user)
        request = create_request(StudyPartnerRequestCreate(recipient_profile_id=partner.id), session, student)
        with pytest.raises(HTTPException) as duplicate:
            create_request(StudyPartnerRequestCreate(recipient_profile_id=student.id), session, partner)
        assert duplicate.value.status_code == 409
        with pytest.raises(HTTPException) as wrong_owner:
            accept_request(request["id"], session, student)
        assert wrong_owner.value.status_code == 404
        assert accept_request(request["id"], session, partner)["status"] == "ACCEPTED"
        with pytest.raises(HTTPException) as repeated_accept:
            accept_request(request["id"], session, partner)
        assert repeated_accept.value.status_code == 409
        with pytest.raises(HTTPException) as accepted_again:
            create_request(StudyPartnerRequestCreate(recipient_profile_id=partner.id), session, student)
        assert accepted_again.value.status_code == 409
        create_block(StudyPartnerBlockCreate(blocked_user_id=partner.id), session, student)
        assert session.get(StudyPartnerRequest, request["id"]).status == "CANCELLED"
        cancelled = create_request(StudyPartnerRequestCreate(recipient_profile_id=student.id), session, third)
        assert cancel_request(cancelled["id"], session, third)["status"] == "CANCELLED"
        with pytest.raises(HTTPException) as cooldown:
            create_request(StudyPartnerRequestCreate(recipient_profile_id=student.id), session, third)
        assert cooldown.value.status_code == 429
        declined = create_request(StudyPartnerRequestCreate(recipient_profile_id=third.id), session, partner)
        assert decline_request(declined["id"], session, third)["status"] == "DECLINED"
        second = create_request(StudyPartnerRequestCreate(recipient_profile_id=fourth.id), session, student)
        create_block(StudyPartnerBlockCreate(blocked_user_id=student.id), session, fourth)
        outgoing = requests(session, student, "outgoing", None)
        assert next(item for item in outgoing if item["id"] == second["id"])["status"] == "CANCELLED"
        with pytest.raises(HTTPException) as blocked:
            create_request(StudyPartnerRequestCreate(recipient_profile_id=fourth.id), session, student)
        assert blocked.value.status_code == 404
        put_my_profile(profile_payload("Ada", topic.id, is_participating=False, is_discoverable=False), session, student)
        with pytest.raises(HTTPException) as paused:
            partners(session, student, [], None, 0, 20)
        assert paused.value.status_code == 409
        assert any(item["status"] == "CANCELLED" for item in requests(session, student, "outgoing", None))
    finally:
        session.close()


def test_hidden_and_paused_profiles_reject_new_requests_without_private_leaks():
    session, student, partner, _, _, _, topic, _ = setup()
    try:
        put_my_profile(profile_payload("Ada", topic.id), session, student)
        put_my_profile(profile_payload("Bela", topic.id, is_discoverable=False), session, partner)
        with pytest.raises(HTTPException) as hidden:
            create_request(StudyPartnerRequestCreate(recipient_profile_id=partner.id), session, student)
        with pytest.raises(HTTPException) as unknown:
            create_request(StudyPartnerRequestCreate(recipient_profile_id=999999), session, student)
        assert hidden.value.status_code == unknown.value.status_code == 404
        assert hidden.value.detail == unknown.value.detail == "Study partner not available"
        with pytest.raises(HTTPException) as hidden_block:
            create_block(StudyPartnerBlockCreate(blocked_user_id=partner.id), session, student)
        with pytest.raises(HTTPException) as unknown_block:
            create_block(StudyPartnerBlockCreate(blocked_user_id=999999), session, student)
        assert hidden_block.value.status_code == unknown_block.value.status_code == 404
        assert hidden_block.value.detail == unknown_block.value.detail == "Study partner not available"
        put_my_profile(profile_payload("Bela", topic.id, is_participating=False, is_discoverable=False), session, partner)
        with pytest.raises(HTTPException) as paused:
            create_request(StudyPartnerRequestCreate(recipient_profile_id=partner.id), session, student)
        assert paused.value.status_code == 404 and "@" not in paused.value.detail
    finally:
        session.close()


def test_cooldown_boundary_and_database_constraints(monkeypatch):
    session, student, partner, _, _, _, topic, _ = setup()
    try:
        put_my_profile(profile_payload("Ada", topic.id), session, student)
        put_my_profile(profile_payload("Bela", topic.id), session, partner)
        request = create_request(StudyPartnerRequestCreate(recipient_profile_id=partner.id), session, student)
        assert decline_request(request["id"], session, partner)["status"] == "DECLINED"
        declined = session.get(StudyPartnerRequest, request["id"])
        assert declined and declined.resolved_at
        import app.routers.study_partner as study_partner_router

        boundary = study_partner_router.utc(declined.resolved_at) + timedelta(hours=24)
        monkeypatch.setattr(study_partner_router, "now", lambda: boundary - timedelta(microseconds=1))
        with pytest.raises(HTTPException) as too_early:
            create_request(StudyPartnerRequestCreate(recipient_profile_id=partner.id), session, student)
        assert too_early.value.status_code == 429
        monkeypatch.setattr(study_partner_router, "now", lambda: boundary)
        assert create_request(StudyPartnerRequestCreate(recipient_profile_id=partner.id), session, student)["status"] == "PENDING"

        with pytest.raises(IntegrityError):
            session.add(StudyPartnerAvailability(profile_user_id=student.id, weekday=9, start_minute=10, end_minute=20))
            session.commit()
        session.rollback()
        with pytest.raises(IntegrityError):
            session.add(StudyPartnerTopic(profile_user_id=student.id, topic_id=999999, purpose="WANT_TO_STUDY"))
            session.commit()
        session.rollback()
        with pytest.raises(IntegrityError):
            session.add(StudyPartnerBlock(blocker_user_id=student.id, blocked_user_id=student.id))
            session.commit()
        session.rollback()
    finally:
        session.close()


def test_request_integrity_error_is_reported_as_a_controlled_conflict(monkeypatch):
    session, student, partner, _, _, _, topic, _ = setup()
    try:
        put_my_profile(profile_payload("Ada", topic.id), session, student)
        put_my_profile(profile_payload("Bela", topic.id), session, partner)

        def conflicting_commit():
            raise IntegrityError("INSERT", {}, Exception("pending pair"))

        monkeypatch.setattr(session, "commit", conflicting_commit)
        with pytest.raises(HTTPException) as conflict:
            create_request(StudyPartnerRequestCreate(recipient_profile_id=partner.id), session, student)
        assert conflict.value.status_code == 409
        assert conflict.value.detail == "A study request is already pending"
    finally:
        session.close()


def test_pending_pair_constraint_and_migration_chain():
    session, student, partner, _, _, _, _, _ = setup()
    try:
        first = StudyPartnerRequest(requester_user_id=student.id, recipient_user_id=partner.id, pair_low_user_id=min(student.id, partner.id), pair_high_user_id=max(student.id, partner.id))
        second = StudyPartnerRequest(requester_user_id=partner.id, recipient_user_id=student.id, pair_low_user_id=min(student.id, partner.id), pair_high_user_id=max(student.id, partner.id))
        session.add(first)
        session.commit()
        session.add(second)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.close()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    revision = script.get_revision("0023")
    assert revision is not None and revision.down_revision == "0022"


def test_accepted_participants_can_exchange_paginated_private_messages():
    session, student, partner, third, _, _, topic, _ = setup()
    try:
        put_my_profile(profile_payload("Ada", topic.id), session, student)
        put_my_profile(profile_payload("Bela", topic.id), session, partner)
        put_my_profile(profile_payload("Csilla", topic.id), session, third)
        request = create_request(StudyPartnerRequestCreate(recipient_profile_id=partner.id), session, student)
        accept_request(request["id"], session, partner)

        first = send_chat_message(request["id"], StudyPartnerMessageCreate(content="  Hello, Bela!  "), session, student)
        second = send_chat_message(request["id"], StudyPartnerMessageCreate(content="Hi Ada, let us study sets."), session, partner)
        assert first["sender_user_id"] == student.id and first["content"] == "Hello, Bela!"
        assert second["sender_user_id"] == partner.id
        assert not hasattr(StudyPartnerMessageCreate.model_validate({"content": "x", "sender_user_id": third.id}), "sender_user_id")

        history = chat_messages(request["id"], session, student, 0, 50)
        assert [message["id"] for message in history] == [first["id"], second["id"]]
        assert chat_messages(request["id"], session, partner, 1, 1)[0]["id"] == second["id"]
        listing = chats(session, student)
        assert listing == [
            {
                "request_id": request["id"],
                "counterpart": {"profile_id": partner.id, "display_name": "Bela"},
                "last_message_preview": "Hi Ada, let us study sets.",
                "last_message_at": second["created_at"],
            }
        ]
        assert "email" not in str(listing).lower() and "neptun" not in str(listing).lower()

        with pytest.raises(HTTPException) as outsider:
            chat_messages(request["id"], session, third, 0, 50)
        assert outsider.value.status_code == 404 and outsider.value.detail == "Conversation not available"
    finally:
        session.close()


def test_chat_rejects_inactive_requests_blocks_and_invalid_content():
    session, student, partner, third, _, _, topic, _ = setup()
    try:
        for user, name in ((student, "Ada"), (partner, "Bela"), (third, "Csilla")):
            put_my_profile(profile_payload(name, topic.id), session, user)
        pending = create_request(StudyPartnerRequestCreate(recipient_profile_id=partner.id), session, student)
        with pytest.raises(HTTPException) as pending_error:
            send_chat_message(pending["id"], StudyPartnerMessageCreate(content="Hello"), session, student)
        assert pending_error.value.status_code == 404 and pending_error.value.detail == "Conversation not available"
        decline_request(pending["id"], session, partner)
        with pytest.raises(HTTPException) as declined_error:
            chat_messages(pending["id"], session, student, 0, 50)
        assert declined_error.value.status_code == 404 and declined_error.value.detail == "Conversation not available"

        accepted = create_request(StudyPartnerRequestCreate(recipient_profile_id=third.id), session, student)
        accept_request(accepted["id"], session, third)
        create_block(StudyPartnerBlockCreate(blocked_user_id=third.id), session, student)
        with pytest.raises(HTTPException) as blocked_error:
            send_chat_message(accepted["id"], StudyPartnerMessageCreate(content="Blocked"), session, student)
        assert blocked_error.value.status_code == 404 and blocked_error.value.detail == "Conversation not available"
        assert session.scalar(text("SELECT count(*) FROM study_partner_messages")) == 0

        for content in ("   ", "x" * 2001, "text\x01"):
            with pytest.raises(ValidationError):
                StudyPartnerMessageCreate(content=content)
    finally:
        session.close()
