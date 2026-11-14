from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import JSON, MetaData, UniqueConstraint, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth import manager_user, utc
from app.auth_models import User
from app.database import Base
from app.exam_models import Exam
from app.exam_schemas import ExamCreate, ExamPatch
from app.document_generation.exams import ExamDocumentType, render_exam_document
from app.models import Question, ResponseType, SkillType, Topic
from app.routers import exams as exam_router
from app.services.exams import create_exam, delete_exam, finalize_exam, get_exam, list_exams, read_exam, update_exam


def sqlite_metadata() -> MetaData:
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
    return metadata


@pytest.fixture
def setup():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sqlite_metadata().create_all(engine)
    session = Session(engine)
    topic = Topic(slug="logic", name="Logic", sort_order=1)
    session.add_all((topic, ResponseType(code="FREE_RESPONSE", label="Free response", sort_order=1), SkillType(code="PROOF", label="Proof", sort_order=1)))
    session.flush()
    questions = [
        Question(topic_id=topic.id, difficulty="easy", response_type="FREE_RESPONSE", skill_type="PROOF", question_text="Prove the first statement.", expected_answer="First reference proof.", explanation="First explanation."),
        Question(topic_id=topic.id, difficulty="medium", response_type="FREE_RESPONSE", skill_type="PROOF", question_text="Prove the second statement.", expected_answer="Second reference proof.", explanation="Second explanation."),
    ]
    lecturer = User(email="lecturer@example.test", password_hash="x", role="LECTURER", email_verified=True)
    student = User(email="student@example.test", password_hash="x", role="STUDENT", email_verified=True)
    demonstrator = User(email="demonstrator@example.test", password_hash="x", role="DEMONSTRATOR", email_verified=True)
    session.add_all((*questions, lecturer, student, demonstrator))
    session.commit()

    yield session, questions, lecturer, student, demonstrator
    session.close()
    engine.dispose()


def payload(questions):
    return {
        "title": "Midterm A",
        "instructions": "Show all reasoning.",
        "questions": [
            {"question_id": questions[0].id, "points": 4},
            {"question_id": questions[1].id, "points": 6},
        ],
    }


def test_exam_crud_validation_and_manager_permissions(setup):
    session, questions, lecturer, student, demonstrator = setup
    assert manager_user(lecturer) is lecturer
    for user in (student, demonstrator):
        with pytest.raises(HTTPException, match="permission") as error:
            manager_user(user)
        assert error.value.status_code == 403

    exam = read_exam(create_exam(session, ExamCreate.model_validate(payload(questions)), lecturer.id))
    assert exam["status"] == "draft" and exam["snapshot_available"] is False
    assert [(entry["question_id"], entry["position"], entry["points"]) for entry in exam["questions"]] == [
        (questions[0].id, 0, 4),
        (questions[1].id, 1, 6),
    ]
    assert list_exams(session, 0, 20)[0]["id"] == exam["id"]

    updated = read_exam(update_exam(
        session,
        exam["id"],
        ExamPatch.model_validate({"questions": [{"question_id": questions[1].id, "points": 7}, {"question_id": questions[0].id, "points": 3}]}),
    ))
    assert [(entry["question_id"], entry["position"], entry["points"]) for entry in updated["questions"]] == [
        (questions[1].id, 0, 7),
        (questions[0].id, 1, 3),
    ]
    with pytest.raises(ValueError):
        ExamCreate.model_validate({**payload(questions), "questions": [{"question_id": questions[0].id, "points": 1}] * 2})
    with pytest.raises(HTTPException) as error:
        create_exam(session, ExamCreate.model_validate({**payload(questions), "questions": [{"question_id": 999999, "points": 1}]}), lecturer.id)
    assert error.value.status_code == 422
    with pytest.raises(ValueError):
        ExamPatch.model_validate({"questions": [{"question_id": questions[0].id, "points": 0}]})


def test_finalization_snapshots_answers_and_blocks_mutation(setup):
    session, questions, lecturer, _, _ = setup
    created = create_exam(session, ExamCreate.model_validate(payload(questions)), lecturer.id)
    finalized = read_exam(finalize_exam(session, created.id))
    assert finalized["status"] == "finalized"
    assert finalized["snapshot_available"] is True
    snapshot = session.get(Exam, created.id).question_snapshot
    assert snapshot and snapshot["questions"][0]["expected_answer"] == "First reference proof."

    questions[0].question_text = "Changed after finalization"
    questions[0].expected_answer = "Changed answer"
    session.commit()
    session.expire_all()
    frozen = session.get(Exam, created.id).question_snapshot
    assert frozen == snapshot
    for operation in (
        lambda: update_exam(session, created.id, ExamPatch.model_validate({"title": "Changed"})),
        lambda: delete_exam(session, created.id),
        lambda: finalize_exam(session, created.id),
    ):
        with pytest.raises(HTTPException) as error:
            operation()
        assert error.value.status_code == 409


def test_draft_delete_empty_finalization_and_utc_normalization(setup):
    session, _, lecturer, _, _ = setup
    created = create_exam(session, ExamCreate.model_validate({"title": "Empty draft"}), lecturer.id)
    with pytest.raises(HTTPException) as error:
        finalize_exam(session, created.id)
    assert error.value.status_code == 422
    delete_exam(session, created.id)
    with pytest.raises(HTTPException) as error:
        get_exam(session, created.id)
    assert error.value.status_code == 404
    assert utc(datetime(2026, 1, 1)).tzinfo == timezone.utc


def test_exam_and_answer_key_documents_are_safe_and_snapshot_based(setup, monkeypatch):
    session, questions, lecturer, _, _ = setup
    questions[0].question_text = (
        r"Classify $\mathbb{N}$, show $\lvert A\rvert \ge 0$, $\varnothing$, and $\bigcap_i A_i\cdots$, use A ∩ B, x², z̄, and √3, "
        r"and reject $\input{unsafe}$."
    )
    questions[0].expected_answer = r"For $0\le k\le n$, $\binom nk=\binom n{n-k}$ and $\operatorname{dom}(R)=A$."
    session.commit()
    exam = create_exam(session, ExamCreate.model_validate(payload(questions)), lecturer.id)
    draft_source = render_exam_document(session, exam.id, ExamDocumentType.EXAM)
    assert r"\mathbb{N}" in draft_source and r"\input{unsafe}" not in draft_source
    assert r"\providecommand{\lvert}{|}" in draft_source
    assert r"\ensuremath{\cap}" in draft_source
    assert r"\ensuremath{{}^{2}}" in draft_source
    assert r"$\overline{z}$" in draft_source
    assert r"\ensuremath{\surd}" in draft_source
    assert r"\emptyset" in draft_source and r"\varnothing" not in draft_source
    assert r"\bigcap_i A_i\cdots" in draft_source
    assert "First reference proof." not in draft_source

    finalized = finalize_exam(session, exam.id)
    exam_source = render_exam_document(session, finalized.id, ExamDocumentType.EXAM)
    key_source = render_exam_document(session, finalized.id, ExamDocumentType.ANSWER_KEY)
    assert "First reference proof." not in exam_source
    assert r"\providecommand{\binom}[2]{{#1 \choose #2}}" in key_source
    assert r"\providecommand{\operatorname}[1]{\mathrm{#1}}" in key_source
    assert r"\providecommand{\mathbb}[1]{\mathrm{#1}}" in key_source
    assert r"\binom nk" in key_source and "First explanation." in key_source
    questions[0].question_text = "Changed after finalization"
    questions[0].expected_answer = "Changed answer"
    session.commit()
    assert render_exam_document(session, finalized.id, ExamDocumentType.EXAM) == exam_source

    monkeypatch.setattr(exam_router, "compile_pdf", lambda source: b"%PDF-1.7\nmock")
    response = exam_router.download_document(finalized.id, ExamDocumentType.EXAM, session, lecturer)
    assert response.body.startswith(b"%PDF-")
    assert response.headers["content-disposition"].endswith('exam.pdf"')
    assert response.headers["cache-control"] == "no-store"
    with pytest.raises(HTTPException) as error:
        render_exam_document(session, 999999, ExamDocumentType.EXAM)
    assert error.value.status_code == 404
    with pytest.raises(ValueError):
        ExamDocumentType("not-a-document")
