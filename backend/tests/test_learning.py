"""Isolated PostgreSQL coverage for student topic-practice and learning history."""
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from fastapi import Response
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.auth import issue_session
from app.auth_models import User
from app.database import get_engine, get_session
from app.main import app
from app.models import Question, Topic
from app.services.learning import learning_summary, practice_topics
from app.services.quizzes import get_attempt, get_quiz, review, save_answer, start_practice_attempt, submit_attempt
from app.schemas import AnswerCheck


pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Set RUN_POSTGRES_TESTS=1")]


@pytest.fixture
def isolated_learning_session():
    """A throwaway migrated schema; never write to local development tables."""
    schema = f"dmi_m11_{uuid4().hex}"
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
        try:
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "0014")
            with Session(connection, join_transaction_mode="create_savepoint") as session:
                yield session
        finally:
            connection.execute(text("SET LOCAL search_path TO public"))
            connection.execute(DropSchema(schema, cascade=True))


def test_private_practice_lifecycle_progress_and_solution_visibility(isolated_learning_session):
    session = isolated_learning_session
    student = User(email="m11-student@example.test", role="STUDENT", email_verified=True)
    another = User(email="m11-other@example.test", role="STUDENT", email_verified=True)
    grader = User(email="m11-grader@example.test", role="LECTURER", email_verified=True)
    session.add_all([student, another, grader])
    logic = session.scalar(select(Topic).where(Topic.slug == "logic"))
    assert logic is not None
    session.add_all([
        Question(external_source_id=f"M10A3:M11-{index}", source_reference="M11 fixture", topic_id=logic.id,
                 title="Practice fixture", difficulty="easy", response_type="FREE_RESPONSE", skill_type="PROOF",
                 question_text=f"Prove fixture {index}.", expected_answer=f"Reference solution {index}.",
                 explanation=f"Explanation {index}.", is_active=True)
        for index in range(3)
    ])
    session.commit()
    grader_id = grader.id

    rows = practice_topics(session, student.id)
    assert next(row for row in rows if row.slug == "logic").available_question_count == 3
    response = Response()
    csrf = issue_session(session, student, response)
    headers = {"Cookie": response.headers["set-cookie"].split(";", 1)[0], "X-CSRF-Token": csrf}
    staff_response = Response()
    staff_csrf = issue_session(session, grader, staff_response)
    staff_headers = {"Cookie": staff_response.headers["set-cookie"].split(";", 1)[0], "X-CSRF-Token": staff_csrf}
    app.dependency_overrides[get_session] = lambda: session
    try:
        with TestClient(app) as client:
            assert client.get("/student/practice/topics").status_code == 401
            assert client.get("/student/practice/topics", headers=staff_headers).status_code == 403
            assert client.get("/student/practice/topics", headers={"Cookie": headers["Cookie"]}).status_code == 200
            assert client.get("/student/practice/topics", headers={"Cookie": headers["Cookie"]}).json()[0].keys() >= {"slug", "available_question_count"}
            assert client.post("/student/practice/sessions", headers={"Cookie": headers["Cookie"]}, json={"topic_slug": "logic", "question_count": 2}).status_code == 403
            active = client.post("/student/practice/sessions", headers=headers, json={"topic_slug": "logic", "question_count": 2})
            assert active.status_code == 201, active.text
            assert "expected_answer" not in active.text and "explanation" not in active.text
            attempt = get_attempt(session, active.json()["id"], student.id)
    finally:
        app.dependency_overrides.pop(get_session, None)
    assert attempt.quiz.is_practice and attempt.quiz.practice_owner_id == student.id
    with pytest.raises(HTTPException, match="Quiz not found"):
        get_quiz(session, attempt.quiz_id)
    assert learning_summary(session, student.id).continue_learning.kind == "RESUME_ATTEMPT"
    with pytest.raises(HTTPException, match="Attempt not found"):
        get_attempt(session, attempt.id, another.id)

    save_answer(session, attempt.id, attempt.items[0].id, student.id, AnswerCheck(free_response="My \u00e1rvas proof."))
    submitted = submit_attempt(session, attempt.id, student.id)
    before_grade = review(submitted)
    assert before_grade["items"][0]["manual_grading_status"] == "PENDING"
    assert before_grade["items"][0]["expected_answer"] == "Reference solution 0."
    item = submitted.items[0]
    item.manual_points = 1
    item.manual_feedback = "Correct reasoning."
    item.graded_by_id = grader_id
    item.graded_at = datetime.now(timezone.utc)
    session.commit()
    summary = learning_summary(session, student.id)
    assert summary.overview.total_attempted_questions == 1
    assert summary.overview.completed_practice_sessions == 1
    assert summary.overview.pending_grading_count == 1
    assert summary.overview.graded_question_count == 1
    logic_row = next(row for row in summary.topics if row.slug == "logic")
    assert logic_row.attempted_question_count == 1 and logic_row.graded_score_percent == 100


def test_practice_rejects_unknown_topics_and_insufficient_curated_questions(isolated_learning_session):
    session = isolated_learning_session
    student = User(email="m11-limit@example.test", role="STUDENT", email_verified=True)
    session.add(student)
    session.commit()
    with pytest.raises(HTTPException, match="Practice topic not found"):
        start_practice_attempt(session, "missing", 1, student.id)
    with pytest.raises(HTTPException, match="Not enough available"):
        start_practice_attempt(session, "graphs", 1, student.id)
