import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.announcement_models import CourseAnnouncement
from app.database import get_engine
from app.main import app


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_POSTGRES_TESTS") != "1",
        reason="Set RUN_POSTGRES_TESTS=1",
    ),
]


@pytest.fixture(autouse=True)
def clean_announcements():
    """Keep the shared disposable PostgreSQL database deterministic."""
    with Session(get_engine()) as session:
        session.execute(delete(CourseAnnouncement))
        session.commit()
    yield
    with Session(get_engine()) as session:
        session.execute(delete(CourseAnnouncement))
        session.commit()


def test_announcements_are_staff_managed_and_student_readable(accounts):
    _, staff = accounts("LECTURER")
    _, student = accounts()
    with TestClient(app) as client:
        draft = client.post(
            "/announcements",
            headers=staff,
            json={"title": "Course update", "body": "Read this update.", "category": "IMPORTANT", "pinned": True},
        )
        assert draft.status_code == 201
        identifier = draft.json()["id"]
        assert client.get("/student/announcements", headers=student).json() == []
        assert client.post(f"/announcements/{identifier}/publish", headers=staff).status_code == 200
        listed = client.get("/student/announcements", headers=student)
        assert listed.status_code == 200
        assert listed.json()[0]["title"] == "Course update"
        assert listed.json()[0]["read_at"] is None
        read = client.post(f"/student/announcements/{identifier}/read", headers=student)
        assert read.status_code == 200 and read.json()["read_at"] is not None


def test_students_cannot_manage_or_read_drafts(accounts):
    _, staff = accounts("ADMIN")
    _, student = accounts()
    with TestClient(app) as client:
        assert client.post("/announcements", headers=student, json={"title": "No", "body": "No"}).status_code == 403
        draft = client.post("/announcements", headers=staff, json={"title": "Draft", "body": "Private"}).json()
        assert client.post(f"/student/announcements/{draft['id']}/read", headers=student).status_code == 404
