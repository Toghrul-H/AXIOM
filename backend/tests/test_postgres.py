import os
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from app.database import get_engine
from app.main import app
from app.models import Question, QuestionOption, Topic, question_problem_sets, question_suitabilities

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Set RUN_POSTGRES_TESTS=1 to use PostgreSQL")]


@pytest.fixture
def client(accounts):
    with TestClient(app) as client:
        _, headers = accounts('LECTURER')
        client.headers.update(headers)
        yield client


@pytest.fixture
def metadata(client):
    response = client.get("/question-metadata")
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def factory(client, metadata):
    created = []
    topic = next(t for t in metadata["topics"] if t["slug"] == "sets")
    def create(kind="FREE_RESPONSE", **changes):
        payload = {
            "topic_id": topic["id"], "difficulty": "easy", "response_type": kind,
            "skill_type": "DEFINITION", "question_text": f"Integration {uuid4().hex}: cardinality of {{a,b}}?",
            "explanation": "Two distinct elements.",
            "problem_set_ids": [p["id"] for p in metadata["problem_sets"][:2]],
            "assessment_suitability_codes": ["GENERAL_PRACTICE", "MIDTERM"],
        }
        if kind == "FREE_RESPONSE": payload["expected_answer"] = "2"
        elif kind == "TRUE_FALSE": payload["correct_boolean"] = False
        else: payload["options"] = [{"text": "a", "is_correct": True}, {"text": "b", "is_correct": kind == "MULTIPLE_SELECT"}, {"text": "c", "is_correct": False}]
        payload.update(changes)
        response = client.post("/questions", json=payload)
        assert response.status_code == 201, response.text
        data = response.json()
        created.append(data["id"])
        assert response.headers["Location"] == f"/questions/{data['id']}"
        return data
    yield create
    with Session(get_engine()) as session:
        for question_id in created:
            row = session.get(Question, question_id)
            if row is not None: session.delete(row)
        session.commit()


def test_database_and_metadata(metadata):
    with get_engine().connect() as connection:
        assert connection.scalar(text("SELECT version()" )).startswith("PostgreSQL")
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0007"
    assert len(metadata["problem_sets"]) == 12
    assert {r["code"] for r in metadata["response_types"]} == {"FREE_RESPONSE", "SINGLE_CHOICE", "MULTIPLE_SELECT", "TRUE_FALSE"}
    assert {t["name"] for t in metadata["topics"] if t["parent_id"] is None} >= {"Foundations", "Complex Numbers", "Combinatorics", "Graphs"}


@pytest.mark.parametrize("kind", ["FREE_RESPONSE", "SINGLE_CHOICE", "MULTIPLE_SELECT", "TRUE_FALSE"])
def test_crud_persistence(client, factory, kind):
    body = factory(kind)
    question_id = body["id"]
    assert body["topic"]["name"] == "Sets"
    assert body["topic"]["parent"]["name"] == "Foundations"
    assert len(body["problem_sets"]) == 2
    assert len(body["assessment_suitabilities"]) == 2
    with Session(get_engine()) as session:
        stored = session.get(Question, question_id)
        assert stored is not None and stored.response_type == kind
        assert len(stored.problem_sets) == 2
        assert len(stored.assessment_suitabilities) == 2
        assert len(stored.options) == len(body["options"])
    assert client.get(f"/questions/{question_id}").json() == body
    update = client.patch(f"/questions/{question_id}", json={"difficulty": "medium", "title": "Updated", "explanation": None, "is_active": False})
    assert update.status_code == 200, update.text
    assert update.json()["updated_at"] >= body["updated_at"]
    with Session(get_engine()) as session:
        updated = session.get(Question, question_id)
        assert updated.difficulty == "medium" and updated.title == "Updated"
        assert updated.explanation is None and not updated.is_active
    assert client.delete(f"/questions/{question_id}").status_code == 204
    with Session(get_engine()) as session:
        assert session.get(Question, question_id) is None
        assert session.scalar(select(func.count()).select_from(QuestionOption).where(QuestionOption.question_id == question_id)) == 0
        for association in (question_problem_sets, question_suitabilities):
            assert session.scalar(select(func.count()).select_from(association).where(association.c.question_id == question_id)) == 0
    assert client.get(f"/questions/{question_id}").status_code == 404
    assert client.patch(f"/questions/{question_id}", json={"title": "Absent"}).status_code == 404
    assert client.delete(f"/questions/{question_id}").status_code == 404
    assert client.post(f"/questions/{question_id}/check", json={}).status_code == 404


def test_filters_and_pagination(client, factory, metadata):
    row = factory("MULTIPLE_SELECT")
    other = factory("FREE_RESPONSE", is_active=False, skill_type="PROOF")
    common = {"q": row["question_text"]}
    filters = [
        {"topic_id": row["topic"]["id"]}, {"topic_id": row["topic"]["parent_id"]},
        {"problem_set_id": row["problem_sets"][1]["id"]}, {"difficulty": "easy"},
        {"response_type": "MULTIPLE_SELECT"}, {"skill_type": "DEFINITION"},
        {"assessment_suitability": "MIDTERM"}, {"is_active": True},
    ]
    combined = dict(common)
    for params in filters:
        result = client.get("/questions", params=common | params).json()
        assert result["total"] == 1 and result["items"][0]["id"] == row["id"]
        combined.update(params)
    assert client.get("/questions", params=combined).json()["total"] == 1
    assert client.get("/questions", params=common | {"topic_id": row["topic"]["parent_id"], "include_descendants": False}).json()["total"] == 0
    assert client.get("/questions", params=common | {"skill_type": "PROOF"}).json()["total"] == 0
    assert client.get("/questions", params=common | {"limit": 1, "offset": 1}).json()["items"] == []
    assert client.get("/questions", params={"q": other["question_text"], "is_active": False}).json()["total"] == 1
    literal = factory(question_text=f"Literal 100%_search {uuid4().hex}")
    assert client.get("/questions", params={"q": literal["question_text"]}).json()["total"] == 1
    assert client.get("/questions?limit=101").status_code == 422


def test_invalid_associations_and_merged_patch(client, factory):
    row = factory()
    for patch in ({"topic_id": 2147483647}, {"skill_type": "UNKNOWN"}, {"problem_set_ids": [2147483647]}, {"assessment_suitability_codes": ["UNKNOWN"]}, {"response_type": "SINGLE_CHOICE"}, {"expected_answer": None}, {}):
        assert client.patch(f"/questions/{row['id']}", json=patch).status_code == 422
    assert client.get(f"/questions/{row['id']}").json() == row
    assert client.patch(f"/questions/{row['id']}", json={"problem_set_ids": [], "assessment_suitability_codes": []}).status_code == 200
    cleared = client.get(f"/questions/{row['id']}").json()
    assert cleared["problem_sets"] == [] and cleared["assessment_suitabilities"] == []


def test_option_identity_reordering_and_type_change(client, factory):
    row = factory("SINGLE_CHOICE")
    another = factory("SINGLE_CHOICE")
    options = [{k: option[k] for k in ("id", "text", "is_correct")} for option in reversed(row["options"])]
    result = client.patch(f"/questions/{row['id']}", json={"options": options})
    assert result.status_code == 200, result.text
    assert [o["id"] for o in result.json()["options"]] == [o["id"] for o in options]
    options[0]["id"] = another["options"][0]["id"]
    assert client.patch(f"/questions/{row['id']}", json={"options": options}).status_code == 422
    result = client.patch(f"/questions/{row['id']}", json={"response_type": "FREE_RESPONSE", "options": [], "expected_answer": "Reference answer"})
    assert result.status_code == 200
    assert result.json()["options"] == []


@pytest.mark.parametrize("kind", ["SINGLE_CHOICE", "MULTIPLE_SELECT", "TRUE_FALSE", "FREE_RESPONSE"])
def test_safe_grading(client, factory, kind):
    row = factory(kind)
    url = f"/questions/{row['id']}/check"
    if kind in ("SINGLE_CHOICE", "MULTIPLE_SELECT"):
        correct = [o["id"] for o in row["options"] if o["is_correct"]]
        assert client.post(url, json={"selected_option_ids": correct[::-1]}).json()["is_correct"] is True
        wrong = [next(o["id"] for o in row["options"] if not o["is_correct"])]
        feedback = client.post(url, json={"selected_option_ids": wrong}).json()
        assert feedback["is_correct"] is False and feedback["explanation"] == row["explanation"]
        assert client.post(url, json={"selected_option_ids": [2147483647]}).status_code == 422
        assert client.post(url, json={"selected_option_ids": [correct[0], correct[0]]}).status_code == 422
        if kind == "MULTIPLE_SELECT":
            assert client.post(url, json={"selected_option_ids": correct[:1]}).json()["is_correct"] is False
            assert client.post(url, json={"selected_option_ids": correct + wrong}).json()["is_correct"] is False
    elif kind == "TRUE_FALSE":
        assert client.post(url, json={"boolean_answer": False}).json()["is_correct"] is True
        assert client.post(url, json={"boolean_answer": True}).json()["is_correct"] is False
        assert client.post(url, json={"boolean_answer": "false"}).status_code == 422
    else:
        result = client.post(url, json={"free_response": "An arbitrary proof"}).json()
        assert result["auto_gradable"] is False and result["is_correct"] is None
        assert result["expected_answer"] == "2"


def test_database_driven_topic(client, factory):
    with Session(get_engine()) as session:
        topic = Topic(name="Temporary test subtopic", slug=f"test-{uuid4().hex}", sort_order=999)
        session.add(topic); session.commit(); topic_id = topic.id
    try:
        assert any(t["id"] == topic_id for t in client.get("/question-metadata").json()["topics"])
        row = factory(topic_id=topic_id)
        assert row["topic"]["name"] == "Temporary test subtopic"
        client.delete(f"/questions/{row['id']}")
    finally:
        with Session(get_engine()) as session:
            for question in session.scalars(select(Question).where(Question.topic_id == topic_id)): session.delete(question)
            session.flush()
            session.delete(session.get(Topic, topic_id)); session.commit()


