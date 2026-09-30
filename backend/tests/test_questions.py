import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.main import app
from app.schemas import AnswerCheck, QuestionCreate, QuestionPatch


@pytest.fixture
def payload():
    return {"topic_id": 1, "difficulty": "easy", "response_type": "FREE_RESPONSE", "skill_type": "DEFINITION", "question_text": "Define a set.", "expected_answer": "A collection of distinct objects."}


def test_root_and_openapi():
    with TestClient(app) as client:
        assert client.get("/").json() == {"message": "DMI Platform API"}
        assert client.get("/docs").status_code == 200
        paths = client.get("/openapi.json").json()["paths"]
        assert {"get", "post"} <= paths["/questions"].keys()
        assert {"get", "patch", "delete"} <= paths["/questions/{question_id}"].keys()
        assert "/question-metadata" in paths
        assert "/questions/{question_id}/check" in paths


@pytest.mark.parametrize("changes", [
    {"topic_id": 0}, {"difficulty": "unknown"}, {"question_text": " "},
    {"response_type": "TRUE_FALSE", "correct_boolean": "yes", "expected_answer": None},
    {"response_type": "TRUE_FALSE", "correct_boolean": None, "expected_answer": None},
    {"response_type": "SINGLE_CHOICE", "expected_answer": None},
    {"response_type": "MULTIPLE_SELECT", "expected_answer": None, "options": [{"text": "a"}, {"text": "b"}]},
    {"options": [{"text": "a"}, {"text": "b"}]}, {"unexpected": "value"},
    {"problem_set_ids": [1, 1]}, {"assessment_suitability_codes": ["MIDTERM", "MIDTERM"]},
    {"expected_answer": None}, {"skill_type": "not-a-code"},
])
def test_invalid_question(payload, changes):
    with pytest.raises(ValidationError):
        QuestionCreate.model_validate(payload | changes)


@pytest.mark.parametrize("options", [
    [{"text": "a", "is_correct": True}],
    [{"text": "a", "is_correct": True}, {"text": " a "}],
    [{"text": "a", "is_correct": True}, {"text": "b", "is_correct": True}],
    [{"text": "a"}, {"text": "b"}],
    [{"id": 1, "text": "a", "is_correct": True}, {"id": 1, "text": "b"}],
])
def test_invalid_single_choice(payload, options):
    with pytest.raises(ValidationError):
        QuestionCreate.model_validate(payload | {"response_type": "SINGLE_CHOICE", "expected_answer": None, "options": options})


@pytest.mark.parametrize("changes", [{}, {"topic_id": None}, {"is_active": None}, {"id": 1}, {"options": None}])
def test_invalid_patch(changes):
    with pytest.raises(ValidationError):
        QuestionPatch.model_validate(changes)


def test_nullable_explanation_patch():
    assert QuestionPatch(explanation=None).model_dump(exclude_unset=True) == {"explanation": None}


def test_duplicate_submission_options():
    with pytest.raises(ValidationError):
        AnswerCheck(selected_option_ids=[1, 1])


def test_skill_and_response_are_independent(payload):
    for skill in ("DEFINITION", "PROOF", "CALCULATION"):
        QuestionCreate.model_validate(payload | {"skill_type": skill})
        QuestionCreate.model_validate(payload | {"skill_type": skill, "response_type": "SINGLE_CHOICE", "expected_answer": None, "options": [{"text": "a", "is_correct": True}, {"text": "b"}]})
