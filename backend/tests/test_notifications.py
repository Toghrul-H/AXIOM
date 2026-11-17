from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import JSON, MetaData, UniqueConstraint, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.auth_models import User
from app.database import Base
from app.notification_models import Notification
from app.routers.notifications import no_store, router
from app.services.notifications import (
    create_notification,
    create_notifications,
    list_notifications,
    mark_all_read,
    mark_read,
    unread_count,
)
from starlette.requests import Request


def sqlite_metadata() -> MetaData:
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        clone = table.to_metadata(metadata)
        for column in clone.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()
        for constraint in clone.constraints:
            if (
                isinstance(constraint, UniqueConstraint)
                and constraint.name
                in {"uq_question_options_position", "uq_quiz_questions_position"}
            ):
                constraint.deferrable = None
                constraint.initially = None
    return metadata


@pytest.fixture
def notification_setup():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    sqlite_metadata().create_all(engine)
    session = Session(engine)
    recipient = User(email="recipient@example.test", password_hash="x")
    other = User(email="other@example.test", password_hash="x")
    actor = User(email="actor@example.test", password_hash="x")
    session.add_all((recipient, other, actor))
    session.commit()
    yield session, recipient, other, actor
    session.close()
    engine.dispose()


def notification(session, recipient_id, *, key="notification:1", actor_id=None):
    return create_notification(
        session,
        recipient_user_id=recipient_id,
        actor_user_id=actor_id,
        kind="STUDY_REQUEST_CREATED",
        dedupe_key=key,
        payload={"title": "Study Partner request", "resource_id": 1},
        link="/student/study-partner",
    )


def test_notification_creation_deduplication_and_transaction_rollback(notification_setup):
    session, recipient, _, actor = notification_setup
    recipient_id, actor_id = recipient.id, actor.id
    session.rollback()
    transaction = session.begin()
    first, created = notification(session, recipient_id, actor_id=actor_id)
    duplicate, duplicate_created = notification(session, recipient_id, actor_id=actor_id)
    assert created and not duplicate_created and duplicate.id == first.id
    transaction.rollback()
    assert session.scalar(select(Notification.id).where(Notification.recipient_user_id == recipient_id)) is None

    first, created = notification(session, recipient_id, actor_id=actor_id)
    session.commit()
    assert created and first.id is not None
    fanout = create_notifications(
        session,
        recipient_user_ids=[recipient_id, recipient_id, actor_id],
        kind="COURSE_LESSON_PUBLISHED",
        dedupe_key="lesson:4:published",
        payload={"title": "New course lesson", "resource_id": 4},
        link="/student/course",
    )
    session.commit()
    assert [(item.recipient_user_id, created) for item, created in fanout] == [
        (recipient_id, True),
        (actor_id, True),
    ]


@pytest.mark.parametrize(
    "payload,link",
    [
        ({"title": "Unsafe"}, "https://example.test"),
        ({"message": "private chat text"}, "/student/study-partner"),
        ({"email": "student@example.test"}, "/student/study-partner"),
        ({"title": ["nested"]}, "/student/study-partner"),
        ({"title": "Unsafe"}, "//example.test"),
    ],
)
def test_notification_rejects_unsafe_links_and_payloads(notification_setup, payload, link):
    session, recipient, _, _ = notification_setup
    with pytest.raises(ValueError):
        create_notification(
            session,
            recipient_user_id=recipient.id,
            kind="STUDY_REQUEST_CREATED",
            dedupe_key="unsafe:1",
            payload=payload,
            link=link,
        )


def test_recipient_isolation_pagination_and_read_operations(notification_setup):
    session, recipient, other, _ = notification_setup
    base = datetime(2026, 11, 18, tzinfo=timezone.utc)
    for index in range(3):
        item, _ = notification(session, recipient.id, key=f"notification:{index}")
        item.created_at = base + timedelta(minutes=index)
    private, _ = notification(session, other.id, key="other:1")
    session.commit()

    first_page, cursor = list_notifications(session, recipient.id, limit=2, cursor=None)
    assert [item.dedupe_key for item in first_page] == ["notification:2", "notification:1"]
    assert cursor
    second_page, final_cursor = list_notifications(session, recipient.id, limit=2, cursor=cursor)
    assert [item.dedupe_key for item in second_page] == ["notification:0"]
    assert final_cursor is None
    assert unread_count(session, recipient.id) == 3

    with pytest.raises(HTTPException) as error:
        mark_read(session, recipient.id, private.id)
    assert error.value.status_code == 404
    assert mark_read(session, recipient.id, first_page[0].id).read_at is not None
    assert unread_count(session, recipient.id) == 2
    assert mark_all_read(session, recipient.id) == 2
    session.commit()
    assert unread_count(session, recipient.id) == 0
    assert unread_count(session, other.id) == 1
    with pytest.raises(HTTPException) as error:
        list_notifications(session, recipient.id, limit=1, cursor="not-a-cursor")
    assert error.value.status_code == 422


def test_notification_routes_require_the_existing_authenticated_user_dependency(notification_setup):
    session, _, _, _ = notification_setup
    routes = {route.path: route for route in router.routes}
    for path in ("/notifications", "/notifications/unread-count", "/notifications/{notification_id}/read", "/notifications/read-all"):
        assert get_current_user in {dependency.call for dependency in routes[path].dependant.dependencies}
    with pytest.raises(HTTPException) as error:
        get_current_user(Request({"type": "http", "method": "GET", "headers": []}), session)
    assert error.value.status_code == 401
    response = Response()
    no_store(response)
    assert response.headers["Cache-Control"] == "no-store"
