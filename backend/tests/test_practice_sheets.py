import pytest
from fastapi import HTTPException
from sqlalchemy import JSON, MetaData, UniqueConstraint, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from starlette.requests import Request

from app.auth import get_current_user, manager_user
from app.auth_models import User
from app.database import Base
from app.document_generation.practice_sheets import PracticeSheetDocumentType, render_practice_sheet_document
from app.models import Question, ResponseType, SkillType, Topic
from app.practice_sheet_models import PracticeSheetVariant
from app.practice_sheet_schemas import PracticeSheetCreate, PracticeSheetPatch, VariantGenerate
from app.services.practice_sheets import (
    create_practice_sheet, delete_practice_sheet, finalize_practice_sheet, generate_variants,
    get_practice_sheet, read_practice_sheet, update_practice_sheet,
)
from app.routers import practice_sheets as practice_sheet_router


def sqlite_metadata() -> MetaData:
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        clone = table.to_metadata(metadata)
        for column in clone.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()
        for constraint in clone.constraints:
            if isinstance(constraint, UniqueConstraint) and constraint.name in {
                "uq_question_options_position", "uq_quiz_questions_position",
            }:
                constraint.deferrable = None
                constraint.initially = None
    return metadata


@pytest.fixture
def setup():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sqlite_metadata().create_all(engine)
    session = Session(engine)
    topic = Topic(slug="logic", name="Logic", sort_order=1)
    session.add_all((topic, ResponseType(code="FREE_RESPONSE", label="Free response", sort_order=1), SkillType(code="PROOF", label="Proof", sort_order=1)))
    session.flush()
    questions = [
        Question(topic_id=topic.id, difficulty="easy", response_type="FREE_RESPONSE", skill_type="PROOF", question_text=f"Prove statement {index}.", expected_answer=f"Reference answer {index}.", explanation=f"Explanation {index}.")
        for index in range(1, 4)
    ]
    lecturer = User(email="lecturer@example.test", password_hash="x", role="LECTURER", email_verified=True)
    admin = User(email="admin@example.test", password_hash="x", role="ADMIN", email_verified=True)
    student = User(email="student@example.test", password_hash="x", role="STUDENT", email_verified=True)
    session.add_all((*questions, lecturer, admin, student))
    session.commit()
    yield session, questions, lecturer, admin, student
    session.close()
    engine.dispose()


def payload(questions):
    return {
        "title": "Logic practice",
        "instructions": "Show every reasoning step.",
        "questions": [
            {"question_id": questions[0].id, "points": 3},
            {"question_id": questions[1].id, "points": None},
            {"question_id": questions[2].id, "points": 5},
        ],
    }


def test_crud_validation_and_manager_restrictions(setup):
    session, questions, lecturer, admin, student = setup
    assert manager_user(lecturer) is lecturer and manager_user(admin) is admin
    with pytest.raises(HTTPException, match="permission") as error:
        manager_user(student)
    assert error.value.status_code == 403
    anonymous = Request({"type": "http", "method": "GET", "headers": []})
    with pytest.raises(HTTPException) as error:
        get_current_user(anonymous, session)
    assert error.value.status_code == 401

    sheet = create_practice_sheet(session, PracticeSheetCreate.model_validate(payload(questions)), lecturer.id)
    read = read_practice_sheet(sheet)
    assert read["status"] == "draft" and [entry["position"] for entry in read["questions"]] == [0, 1, 2]
    assert "question_snapshot" not in str(read) and "Reference answer 1." not in str(read)
    updated = update_practice_sheet(session, sheet.id, PracticeSheetPatch.model_validate({
        "questions": [{"question_id": questions[2].id, "points": 7}, {"question_id": questions[0].id, "points": None}],
    }))
    assert [(entry.question_id, entry.position, entry.points) for entry in updated.questions] == [
        (questions[2].id, 0, 7), (questions[0].id, 1, None),
    ]
    with pytest.raises(ValueError):
        PracticeSheetCreate.model_validate({**payload(questions), "questions": [{"question_id": questions[0].id}] * 2})
    with pytest.raises(HTTPException) as error:
        create_practice_sheet(session, PracticeSheetCreate.model_validate({
            "title": "Invalid", "questions": [{"question_id": 999999}],
        }), lecturer.id)
    assert error.value.status_code == 422


def test_deterministic_variants_are_distinct_and_snapshots_private(setup):
    session, questions, lecturer, _, _ = setup
    first = create_practice_sheet(session, PracticeSheetCreate.model_validate(payload(questions)), lecturer.id)
    variants = generate_variants(session, first.id, VariantGenerate.model_validate({
        "labels": ["A", "B"], "seed": "semester-2026", "question_count": 2,
    }))
    assert [variant.label for variant in variants] == ["A", "B"]
    snapshots = [variant.question_snapshot for variant in variants]
    assert all(len(snapshot["questions"]) == 2 and len({item["question_id"] for item in snapshot["questions"]}) == 2 for snapshot in snapshots)
    assert tuple(item["question_id"] for item in snapshots[0]["questions"]) != tuple(item["question_id"] for item in snapshots[1]["questions"])
    assert snapshots[0]["questions"][0]["expected_answer"].startswith("Reference answer")
    assert "Reference answer" not in str(read_practice_sheet(get_practice_sheet(session, first.id)))

    second = create_practice_sheet(session, PracticeSheetCreate.model_validate(payload(questions)), lecturer.id)
    regenerated = generate_variants(session, second.id, VariantGenerate.model_validate({
        "labels": ["A", "B"], "seed": "semester-2026", "question_count": 2,
    }))
    assert [variant.question_snapshot["questions"] for variant in regenerated] == [snapshot["questions"] for snapshot in snapshots]
    with pytest.raises(HTTPException) as error:
        generate_variants(session, first.id, VariantGenerate.model_validate({"labels": ["A"], "seed": "other"}))
    assert error.value.status_code == 409
    questions[0].question_text = "Changed after generation"
    questions[0].expected_answer = "Changed answer"
    session.commit()
    assert session.get(PracticeSheetVariant, variants[0].id).question_snapshot == snapshots[0]


def test_finalization_blocks_mutation_and_invalid_generation(setup):
    session, questions, lecturer, _, _ = setup
    sheet = create_practice_sheet(session, PracticeSheetCreate.model_validate(payload(questions)), lecturer.id)
    with pytest.raises(HTTPException) as error:
        finalize_practice_sheet(session, sheet.id)
    assert error.value.status_code == 422
    with pytest.raises(HTTPException) as error:
        generate_variants(session, sheet.id, VariantGenerate.model_validate({"labels": ["A"], "seed": "s", "question_count": 4}))
    assert error.value.status_code == 422
    generate_variants(session, sheet.id, VariantGenerate.model_validate({"labels": ["A"], "seed": "s"}))
    finalized = finalize_practice_sheet(session, sheet.id)
    assert finalized.status == "finalized" and finalized.finalized_at is not None
    for operation in (
        lambda: update_practice_sheet(session, sheet.id, PracticeSheetPatch.model_validate({"title": "Changed"})),
        lambda: delete_practice_sheet(session, sheet.id),
        lambda: generate_variants(session, sheet.id, VariantGenerate.model_validate({"labels": ["B"], "seed": "s"})),
        lambda: finalize_practice_sheet(session, sheet.id),
    ):
        with pytest.raises(HTTPException) as error:
            operation()
        assert error.value.status_code == 409


def test_document_settings_defaults_validation_and_finalization_consistency(setup):
    session, questions, lecturer, _, _ = setup
    # Existing clients omit document_settings and receive safe backward-compatible defaults.
    sheet = create_practice_sheet(session, PracticeSheetCreate.model_validate(payload(questions)), lecturer.id)
    assert sheet.document_settings["header"]["institution_name"] == "Eötvös Loránd University"
    assert sheet.document_settings["layout"] == {
        "paper_size": "A4", "margins": "normal", "question_spacing": "normal",
    }

    settings = {
        "header": {"instructor_name": "Dr. Example", "document_date": "2026-11-13", "logo_visible": False},
        "layout": {"margins": "wide", "question_spacing": "spacious"},
        "questions": {"show_points": False, "answer_space": "large", "page_break_before_question_ids": [questions[1].id]},
    }
    updated = update_practice_sheet(session, sheet.id, PracticeSheetPatch.model_validate({"document_settings": settings}))
    assert updated.document_settings["header"]["document_date"] == "2026-11-13"
    assert updated.document_settings["questions"]["page_break_before_question_ids"] == [questions[1].id]
    assert read_practice_sheet(updated)["document_settings"] == updated.document_settings

    with pytest.raises(ValueError):
        PracticeSheetPatch.model_validate({"document_settings": {"layout": {"margins": "custom"}}})
    with pytest.raises(HTTPException) as error:
        update_practice_sheet(session, sheet.id, PracticeSheetPatch.model_validate({
            "document_settings": {"questions": {"page_break_before_question_ids": [999999]}},
        }))
    assert error.value.status_code == 422

    variant = generate_variants(session, sheet.id, VariantGenerate.model_validate({"labels": ["A"], "seed": "settings"}))[0]
    snapshot = variant.question_snapshot.copy()
    finalized = finalize_practice_sheet(session, sheet.id)
    assert finalized.document_settings == updated.document_settings
    with pytest.raises(HTTPException) as error:
        update_practice_sheet(session, sheet.id, PracticeSheetPatch.model_validate({"document_settings": settings}))
    assert error.value.status_code == 409
    assert session.get(PracticeSheetVariant, variant.id).question_snapshot == snapshot


def test_variant_documents_are_snapshot_based_and_confidential(setup, monkeypatch):
    session, questions, lecturer, _, student = setup
    sheet = create_practice_sheet(session, PracticeSheetCreate.model_validate(payload(questions)), lecturer.id)
    variant = generate_variants(session, sheet.id, VariantGenerate.model_validate({"labels": ["A"], "seed": "pdf"}))[0]
    student_source = render_practice_sheet_document(session, sheet.id, variant.id, PracticeSheetDocumentType.SHEET)
    key_source = render_practice_sheet_document(session, sheet.id, variant.id, PracticeSheetDocumentType.ANSWER_KEY)
    assert "Reference answer 1." not in student_source
    assert "Reference answer" in key_source and "Explanation" in key_source
    questions[0].question_text = "Changed after generation"
    questions[0].expected_answer = "Changed after generation"
    session.commit()
    assert render_practice_sheet_document(session, sheet.id, variant.id, PracticeSheetDocumentType.SHEET) == student_source

    other = create_practice_sheet(session, PracticeSheetCreate.model_validate(payload(questions)), lecturer.id)
    with pytest.raises(HTTPException) as error:
        render_practice_sheet_document(session, other.id, variant.id, PracticeSheetDocumentType.SHEET)
    assert error.value.status_code == 404
    variant.question_snapshot = {"version": 1, "questions": []}
    session.commit()
    with pytest.raises(HTTPException) as error:
        render_practice_sheet_document(session, sheet.id, variant.id, PracticeSheetDocumentType.SHEET)
    assert error.value.status_code == 422
    with pytest.raises(ValueError):
        PracticeSheetDocumentType("unsupported")
    with pytest.raises(HTTPException, match="permission") as error:
        manager_user(student)
    assert error.value.status_code == 403

    variant.question_snapshot = generate_variants(session, other.id, VariantGenerate.model_validate({"labels": ["B"], "seed": "pdf"}))[0].question_snapshot
    session.commit()
    monkeypatch.setattr(practice_sheet_router, "compile_pdf", lambda source: b"%PDF-1.7\nmock")
    response = practice_sheet_router.download_document(
        sheet.id, variant.id, PracticeSheetDocumentType.SHEET, session, lecturer
    )
    assert response.body.startswith(b"%PDF-")
    assert response.headers["content-disposition"].endswith('sheet.pdf"')
    assert response.headers["cache-control"] == "no-store"


def test_variant_documents_apply_validated_document_settings(setup):
    session, questions, lecturer, _, _ = setup
    sheet = create_practice_sheet(session, PracticeSheetCreate.model_validate(payload(questions)), lecturer.id)
    settings = {
        "header": {
            "institution_name": "ELTE_50%",
            "course_name": "DMI & Logic",
            "instructor_name": "Dr. Example",
            "document_date": "2026-11-13",
        },
        "layout": {"margins": "wide", "question_spacing": "spacious"},
        "questions": {
            "show_points": False,
            "answer_space": "large",
            "numbering_enabled": False,
            "page_break_before_question_ids": [questions[1].id],
        },
    }
    update_practice_sheet(session, sheet.id, PracticeSheetPatch.model_validate({"document_settings": settings}))
    variant = generate_variants(session, sheet.id, VariantGenerate.model_validate({"labels": ["A"], "seed": "document-settings"}))[0]
    student = render_practice_sheet_document(session, sheet.id, variant.id, PracticeSheetDocumentType.SHEET)
    key = render_practice_sheet_document(session, sheet.id, variant.id, PracticeSheetDocumentType.ANSWER_KEY)
    assert r"ELTE\_50\%" in student and r"DMI \& Logic" in student
    assert "Instructor: Dr. Example" in student and "2026-11-13" in student
    assert r"margin=28mm" in student and r"\setlength{\parskip}{12pt}" in student
    assert r"\item[]" in student and r"(3 points)" not in student
    assert r"\clearpage" in student and r"\vspace{45mm}\hrule" in student
    assert "Reference answer" not in student
    assert "Reference answer" in key and r"\vspace{45mm}\hrule" not in key

    for answer_space, marker in (("none", None), ("small", "18mm"), ("medium", "30mm")):
        update_practice_sheet(session, sheet.id, PracticeSheetPatch.model_validate({
            "document_settings": {"questions": {"answer_space": answer_space}},
        }))
        rendered = render_practice_sheet_document(session, sheet.id, variant.id, PracticeSheetDocumentType.SHEET)
        assert (r"\vspace" not in rendered) if marker is None else (rf"\vspace{{{marker}}}\hrule" in rendered)

    finalized = finalize_practice_sheet(session, sheet.id)
    frozen_source = render_practice_sheet_document(session, finalized.id, variant.id, PracticeSheetDocumentType.SHEET)
    with pytest.raises(HTTPException):
        update_practice_sheet(session, sheet.id, PracticeSheetPatch.model_validate({"document_settings": settings}))
    assert render_practice_sheet_document(session, finalized.id, variant.id, PracticeSheetDocumentType.SHEET) == frozen_source
