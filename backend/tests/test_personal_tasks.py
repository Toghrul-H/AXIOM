import os

import pytest
from fastapi.testclient import TestClient

from app.main import app


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_POSTGRES_TESTS") != "1",
        reason="Set RUN_POSTGRES_TESTS=1",
    ),
]


def test_tasks_require_an_active_student(accounts):
    _, student = accounts()
    _, staff = accounts("LECTURER")
    with TestClient(app) as client:
        assert client.get("/student/tasks").status_code == 401
        assert client.get("/student/tasks", headers=staff).status_code == 403
        assert client.get("/student/tasks", headers=student).json() == []


def test_task_crud_is_private_and_orders_due_dates(accounts):
    _, first = accounts()
    _, second = accounts()
    with TestClient(app) as client:
        later = client.post(
            "/student/tasks",
            headers=first,
            json={"title": "Later", "due_date": "2026-12-03", "completed": False},
        )
        early = client.post(
            "/student/tasks",
            headers=first,
            json={"title": "Earlier", "due_date": "2026-12-01", "completed": False},
        )
        assert later.status_code == early.status_code == 201
        task = early.json()
        assert [item["title"] for item in client.get("/student/tasks", headers=first).json()] == [
            "Earlier",
            "Later",
        ]
        assert client.get("/student/tasks", headers=second).json() == []
        assert client.put(
            f"/student/tasks/{task['id']}",
            headers=second,
            json={"title": "No", "completed": True},
        ).status_code == 404
        complete = client.put(
            f"/student/tasks/{task['id']}",
            headers=first,
            json={"title": "Earlier", "due_date": "2026-12-01", "completed": True},
        )
        assert complete.status_code == 200
        assert complete.json()["completed_at"] is not None
        assert client.delete(f"/student/tasks/{task['id']}", headers=first).status_code == 204


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "   ", "completed": False},
        {"title": "Outside range", "due_date": "1999-12-31", "completed": False},
        {"title": "Wrong", "completed": "yes"},
    ],
)
def test_task_validation(accounts, payload):
    _, headers = accounts()
    with TestClient(app) as client:
        assert client.post("/student/tasks", headers=headers, json=payload).status_code == 422
