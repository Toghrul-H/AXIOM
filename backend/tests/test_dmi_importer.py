import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi import Response
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.auth import issue_session
from app.auth_models import User
from app.database import get_engine, get_session
from app.importers.dmi_verified import (
    BATCHES,
    DatasetValidationError,
    ImportItem,
    M10C_IDS,
    M10C_METADATA,
    import_items,
    load_import_batch,
    load_m10c_dataset,
    load_verified_dataset,
)
from app.models import Question, Topic
from app.services.grading import check_answer
from app.schemas import AnswerCheck
from app.main import app


def bundle(tmp_path: Path, mutate=None):
    question_id = "M10A-aaaaaaaaaaaa"
    ready = {"candidate_count": 1, "items": [{
        "stable_question_id": question_id, "title": "Validated definition", "source_reference": "Source.pdf p.1 q.1",
        "question_text": "Define a relation.", "expected_answer": "A subset of a Cartesian product.",
        "explanation": "This is the standard definition.", "response_type": "FREE_RESPONSE",
    }]}
    canonical = {"records": [{"stable_question_id": question_id, "source_reference": "Source.pdf p.1 q.1",
        "solution_status": "verified_derived_solution", "final_answer": "A subset of a Cartesian product.",
        "worked_solution": "This is the standard definition."}]}
    evidence = {"records": [{"stable_question_id": question_id, "solution_status": "verified_derived_solution", "evidence": "Definition checked."}]}
    grading = {"records": [{"stable_question_id": question_id, "response_type": "FREE_RESPONSE", "schema_compatible": True, "import_eligible": True}]}
    if mutate:
        mutate(ready, canonical, evidence, grading)
    paths = {"ready": tmp_path / "ready.json", "canonical": tmp_path / "canonical-solutions.json", "evidence": tmp_path / "verification-evidence.json", "grading": tmp_path / "grading-configurations.json"}
    for key, data in (("ready", ready), ("canonical", canonical), ("evidence", evidence), ("grading", grading)):
        paths[key].write_text(json.dumps(data), encoding="utf-8")
    return paths, frozenset({question_id}), {question_id: ("sets", "easy", "DEFINITION")}


def load(paths, expected, metadata):
    return load_verified_dataset(paths["ready"], paths["canonical"], paths["evidence"], paths["grading"], expected, metadata, len(expected))


def m10c_bundle(tmp_path: Path, mutate=None):
    names = {"binary-relations": "Binary Relations", "complex-numbers": "Complex Numbers", "combinatorics": "Combinatorics"}
    records = []
    verification = []
    ready_items = []
    evidence_dir = tmp_path / "source-page-evidence"
    evidence_dir.mkdir()
    for index, question_id in enumerate(sorted(M10C_IDS), start=1):
        topic_slug, _, _ = M10C_METADATA[question_id]
        relative_evidence = f"source-page-evidence/{question_id}.png"
        (evidence_dir / f"{question_id}.png").write_bytes(b"test evidence")
        statement = f"Recovered statement {question_id}."
        answer = f"Verified answer {question_id}."
        solution = f"Worked solution {question_id}."
        source = f"Source.pdf p.{index} q.1"
        records.append({
            "stable_question_id": question_id, "external_source_id": f"M10A3:{question_id}",
            "original_source_path": "Source.pdf", "source_page": index, "source_reference": source,
            "source_page_evidence": relative_evidence, "primary_topic": names[topic_slug],
            "corrected_mathematical_statement": statement, "final_answer": answer,
            "worked_solution": solution, "solution_status": "verified_derived_solution",
            "remaining_uncertainties": None,
        })
        verification.append({"stable_question_id": question_id, "solution_status": "verified_derived_solution", "method": "local enumeration", "evidence": "Independent test evidence.", "computed": {"check": index}})
        ready_items.append({"stable_question_id": question_id, "external_source_id": f"M10A3:{question_id}", "title": f"Recovered {names[topic_slug]} question", "source_reference": source, "question_text": statement, "expected_answer": answer, "explanation": solution, "response_type": "FREE_RESPONSE"})
    ready = {"candidate_count": len(ready_items), "items": ready_items}
    master = {"record_count": len(records), "records": records}
    verified = {"verified_count": len(verification), "records": verification}
    if mutate:
        mutate(ready, master, verified)
    paths = {"ready": tmp_path / "m10c-import-ready.json", "master": tmp_path / "recovered-question-master.json", "evidence": tmp_path / "solution-verification.json"}
    for key, data in (("ready", ready), ("master", master), ("evidence", verified)):
        paths[key].write_text(json.dumps(data), encoding="utf-8")
    return paths


def test_valid_dataset_is_cross_validated(tmp_path):
    paths, expected, metadata = bundle(tmp_path)
    items = load(paths, expected, metadata)
    assert len(items) == 1
    assert items[0].external_source_id == "M10A3:M10A-aaaaaaaaaaaa"
    assert items[0].response_type == "FREE_RESPONSE"


@pytest.mark.parametrize("mutate", [
    lambda ready, canonical, evidence, grading: ready["items"][0].pop("source_reference"),
    lambda ready, canonical, evidence, grading: evidence["records"][0].update(solution_status="generated_needs_review"),
    lambda ready, canonical, evidence, grading: grading["records"][0].update(response_type="SINGLE_CHOICE"),
    lambda ready, canonical, evidence, grading: ready.update(candidate_count=2),
])
def test_invalid_dataset_is_rejected_before_database_access(tmp_path, mutate):
    paths, expected, metadata = bundle(tmp_path, mutate)
    with pytest.raises(DatasetValidationError):
        load(paths, expected, metadata)


def test_duplicate_and_invalid_canonical_ids_are_rejected(tmp_path):
    paths, expected, metadata = bundle(tmp_path)
    ready = json.loads(paths["ready"].read_text())
    ready["items"].append(dict(ready["items"][0]))
    ready["candidate_count"] = 2
    paths["ready"].write_text(json.dumps(ready), encoding="utf-8")
    with pytest.raises(DatasetValidationError, match="duplicates"):
        load(paths, expected, metadata)
    paths, expected, metadata = bundle(tmp_path)
    data = json.loads(paths["ready"].read_text())
    data["items"][0]["stable_question_id"] = "not-a-canonical-id"
    paths["ready"].write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(DatasetValidationError):
        load(paths, expected, metadata)


def test_m10c_batch_is_cross_validated_and_registry_is_closed(tmp_path):
    paths = m10c_bundle(tmp_path)
    items = load_m10c_dataset(paths["ready"], paths["master"], paths["evidence"])
    assert len(items) == 14
    assert {item.canonical_id for item in items} == M10C_IDS
    assert {item.external_source_id for item in items} == {f"M10A3:{question_id}" for question_id in M10C_IDS}
    assert BATCHES["m10a3"].expected_count == 23 and BATCHES["m10c"].expected_count == 14
    with pytest.raises(DatasetValidationError, match="Unknown import batch"):
        load_import_batch("unknown", paths["ready"])


@pytest.mark.parametrize("mutate", [
    lambda ready, master, verified: verified["records"][0].pop("computed"),
    lambda ready, master, verified: verified["records"][0].update(solution_status="generated_needs_review"),
    lambda ready, master, verified: ready["items"][0].update(response_type="SINGLE_CHOICE"),
    lambda ready, master, verified: ready["items"].append(dict(ready["items"][0])),
])
def test_m10c_missing_evidence_invalid_status_response_or_duplicate_is_rejected(tmp_path, mutate):
    paths = m10c_bundle(tmp_path, mutate)
    if len(paths["ready"].read_text(encoding="utf-8")):
        # Keep the count truthful for the duplicate-ID case so _index is the failure.
        ready = json.loads(paths["ready"].read_text(encoding="utf-8"))
        ready["candidate_count"] = len(ready["items"])
        paths["ready"].write_text(json.dumps(ready), encoding="utf-8")
    with pytest.raises(DatasetValidationError):
        load_m10c_dataset(paths["ready"], paths["master"], paths["evidence"])


def integration_item(external_id: str) -> ImportItem:
    return ImportItem(
        canonical_id=external_id, title="M10B importer integration fixture", source_reference="test fixture p.1",
        question_text="Define an importer fixture.", expected_answer="A test-only reference answer.",
        explanation="A test-only worked solution.", topic_slug="sets", difficulty="easy", skill_type="DEFINITION",
    )


@pytest.fixture
def isolated_import_session():
    """A migrated throwaway schema; public development tables are never used."""
    schema = f"dmi_m10b_{uuid4().hex}"
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
        try:
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "0013")
            with Session(connection, join_transaction_mode="create_savepoint") as session:
                yield session
        finally:
            connection.execute(text("SET LOCAL search_path TO public"))
            connection.execute(DropSchema(schema, cascade=True))


@pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="requires local PostgreSQL")
def test_import_is_dry_run_idempotent_and_manual_grading_compatible(isolated_import_session):
    item = integration_item(f"M10A-{uuid4().hex[:12]}")
    external = item.external_source_id
    session = isolated_import_session
    dry = import_items(session, [item], dataset="test", dry_run=True)
    assert dry.created == 1
    assert dry.topic_distribution == {"sets": 1}
    assert session.scalar(select(Question).where(Question.external_source_id == external)) is None
    applied = import_items(session, [item], dataset="test", dry_run=False)
    assert applied.created == 1
    question = session.scalar(select(Question).where(Question.external_source_id == external))
    assert question and question.source_reference == item.source_reference
    feedback = check_answer(question, AnswerCheck(free_response="student proof"))
    assert feedback.auto_gradable is False and feedback.is_correct is None
    again = import_items(session, [item], dataset="test", dry_run=False)
    assert again.created == 0 and again.skipped == 1


@pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="requires local PostgreSQL")
def test_conflict_and_atomic_rollback_do_not_overwrite_or_leave_rows(isolated_import_session):
    item = integration_item(f"M10A-{uuid4().hex[:12]}")
    external = item.external_source_id
    session = isolated_import_session
    topic_id = session.scalar(select(Topic.id).where(Topic.slug == "sets"))
    assert topic_id is not None
    session.add(Question(external_source_id=external, source_reference="old source", topic_id=topic_id,
        title="old", difficulty="easy", response_type="FREE_RESPONSE", skill_type="DEFINITION", question_text="old", expected_answer="old", explanation="old", is_active=True))
    session.commit()
    report = import_items(session, [item], dataset="test", dry_run=False)
    assert report.conflicts and report.created == 0
    assert session.scalar(select(Question.question_text).where(Question.external_source_id == external)) == "old"
    duplicate = integration_item(f"M10A-{uuid4().hex[:12]}")
    with pytest.raises(IntegrityError):
        import_items(session, [duplicate, duplicate], dataset="test", dry_run=False)
    assert session.scalar(select(Question).where(Question.external_source_id == duplicate.external_source_id)) is None


@pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="requires local PostgreSQL")
def test_m10c_batch_is_atomic_idempotent_and_preserves_existing_records(isolated_import_session, tmp_path):
    session = isolated_import_session
    paths = m10c_bundle(tmp_path)
    items = load_m10c_dataset(paths["ready"], paths["master"], paths["evidence"])
    topic_id = session.scalar(select(Topic.id).where(Topic.slug == "sets"))
    assert topic_id is not None
    existing = Question(topic_id=topic_id, title="Existing fixture", difficulty="easy", response_type="FREE_RESPONSE", skill_type="DEFINITION", question_text="Existing question", expected_answer="Existing answer", explanation="Existing explanation", is_active=True)
    user = User(email=f"preserved-{uuid4().hex}@example.test", password_hash="unchanged", role="STUDENT")
    session.add_all((existing, user)); session.commit()
    existing_id, user_id = existing.id, user.id

    dry = import_items(session, items, dataset="m10c-test", dry_run=True)
    assert dry.created == 14 and dry.skipped == 0 and not dry.conflicts and not dry.rejected
    assert session.get(Question, existing_id).question_text == "Existing question"
    assert session.get(User, user_id).email == user.email

    applied = import_items(session, items, dataset="m10c-test", dry_run=False)
    assert applied.created == 14 and applied.skipped == 0
    persisted = list(session.scalars(select(Question).where(Question.external_source_id.in_([item.external_source_id for item in items]))))
    assert len(persisted) == 14
    assert all(question.response_type == "FREE_RESPONSE" and question.expected_answer and question.explanation for question in persisted)
    assert session.get(Question, existing_id).question_text == "Existing question"
    assert session.get(User, user_id).email == user.email
    again = import_items(session, items, dataset="m10c-test", dry_run=False)
    assert again.created == 0 and again.skipped == 14 and not again.conflicts and not again.rejected


@pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="requires local PostgreSQL")
def test_imported_free_response_works_through_question_quiz_and_grading_apis(isolated_import_session):
    """Exercise the imported-question workflow without touching public development tables."""
    session = isolated_import_session
    item = integration_item(f"M10A-{uuid4().hex[:12]}")
    assert import_items(session, [item], dataset="test", dry_run=False).created == 1
    question = session.scalar(select(Question).where(Question.external_source_id == item.external_source_id))
    assert question is not None
    student = User(email=f"student-{uuid4().hex}@example.test", password_hash="test", role="STUDENT")
    stranger = User(email=f"stranger-{uuid4().hex}@example.test", password_hash="test", role="STUDENT")
    staff = User(email=f"staff-{uuid4().hex}@example.test", password_hash="test", role="LECTURER")
    session.add_all((student, stranger, staff))
    session.commit()

    def headers_for(user: User) -> dict[str, str]:
        response = Response()
        csrf = issue_session(session, user, response)
        return {"Cookie": response.headers["set-cookie"].split(";", 1)[0], "X-CSRF-Token": csrf}

    student_headers, stranger_headers, staff_headers = map(headers_for, (student, stranger, staff))

    def isolated_session():
        yield session

    app.dependency_overrides[get_session] = isolated_session
    try:
        with TestClient(app) as client:
            client.headers.update(staff_headers)
            listing = client.get(f"/questions?topic_id={question.topic_id}&response_type=FREE_RESPONSE")
            assert listing.status_code == 200
            assert [row["id"] for row in listing.json()["items"]] == [question.id]
            detail = client.get(f"/questions/{question.id}")
            assert detail.status_code == 200 and detail.json()["expected_answer"] == item.expected_answer

            quiz = client.post("/quizzes", json={"title": "Imported-question test", "status": "ACTIVE", "questions": [{"question_id": question.id, "points": 2}]})
            assert quiz.status_code == 201
            assert client.post("/quizzes", headers={"Cookie": staff_headers["Cookie"], "X-CSRF-Token": ""}, json={"title": "No CSRF", "status": "ACTIVE", "questions": [{"question_id": question.id, "points": 2}]}).status_code == 403

            active = client.post(f"/student/quizzes/{quiz.json()['id']}/attempts", headers=student_headers)
            assert active.status_code == 201
            active_item = active.json()["items"][0]
            assert "expected_answer" not in active_item and "explanation" not in active_item
            answer = client.put(f"/student/attempts/{active.json()['id']}/answers/{active_item['id']}", headers=student_headers, json={"free_response": "A student proof."})
            assert answer.status_code == 200
            assert client.get(f"/student/attempts/{active.json()['id']}", headers=stranger_headers).status_code == 404
            assert client.get("/grading/attempts", headers=student_headers).status_code == 403

            review = client.post(f"/student/attempts/{active.json()['id']}/submit", headers=student_headers)
            assert review.status_code == 200
            reviewed_item = review.json()["items"][0]
            assert reviewed_item["expected_answer"] == item.expected_answer
            assert reviewed_item["explanation"] == item.explanation
            assert reviewed_item["manual_grading_status"] == "PENDING"

            graded = client.put(f"/grading/attempts/{active.json()['id']}/answers/{active_item['id']}", headers=staff_headers, json={"points": 2, "feedback": "Correct."})
            assert graded.status_code == 200
            assert graded.json()["items"][0]["manual_points"] == 2
    finally:
        app.dependency_overrides.pop(get_session, None)
