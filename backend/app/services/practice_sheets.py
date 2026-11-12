"""Transactional staff practice-sheet composition and deterministic variants."""
from datetime import datetime, timezone
from random import Random

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import Question
from app.practice_sheet_models import PracticeSheet, PracticeSheetQuestion, PracticeSheetVariant
from app.practice_sheet_schemas import (
    PracticeSheetCreate, PracticeSheetPatch, PracticeSheetQuestionWrite, VariantGenerate,
)

_GENERATOR_VERSION = "question-set-v1"


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "Conflicting practice-sheet data") from None


def get_practice_sheet(session: Session, sheet_id: int, *, lock: bool = False) -> PracticeSheet:
    statement = select(PracticeSheet).where(PracticeSheet.id == sheet_id)
    if lock:
        statement = statement.with_for_update()
    sheet = session.scalar(statement)
    if sheet is None:
        raise HTTPException(404, "Practice sheet not found")
    return sheet


def _variant_read(variant: PracticeSheetVariant) -> dict:
    snapshot = variant.question_snapshot if isinstance(variant.question_snapshot, dict) else {}
    questions = snapshot.get("questions")
    return {
        "id": variant.id,
        "label": variant.label,
        "seed": variant.seed,
        "generator_version": variant.generator_version,
        "generated_at": variant.generated_at,
        "question_count": len(questions) if isinstance(questions, list) else 0,
    }


def read_practice_sheet(sheet: PracticeSheet) -> dict:
    return {
        "id": sheet.id,
        "title": sheet.title,
        "instructions": sheet.instructions,
        "status": sheet.status,
        "created_by_id": sheet.created_by_id,
        "finalized_at": sheet.finalized_at,
        "created_at": sheet.created_at,
        "updated_at": sheet.updated_at,
        "questions": [
            {"question_id": entry.question_id, "points": entry.points, "position": entry.position}
            for entry in sheet.questions
        ],
        # Snapshots contain answer material and are intentionally never serialized here.
        "variants": [_variant_read(variant) for variant in sheet.variants],
    }


def list_practice_sheets(session: Session, offset: int, limit: int) -> list[dict]:
    sheets = session.scalars(
        select(PracticeSheet).order_by(PracticeSheet.updated_at.desc(), PracticeSheet.id.desc()).offset(offset).limit(limit)
    ).all()
    return [read_practice_sheet(sheet) for sheet in sheets]


def _active_questions(session: Session, entries: list[PracticeSheetQuestionWrite]) -> dict[int, Question]:
    ids = [entry.question_id for entry in entries]
    if not ids:
        return {}
    rows = session.scalars(
        select(Question).where(Question.id.in_(ids)).options(selectinload(Question.options), selectinload(Question.topic))
    ).all()
    if len(rows) != len(ids):
        raise HTTPException(422, "Unknown question in practice sheet")
    if any(not question.is_active for question in rows):
        raise HTTPException(422, "Practice sheets require active questions")
    return {question.id: question for question in rows}


def _replace_questions(session: Session, sheet: PracticeSheet, entries: list[PracticeSheetQuestionWrite]) -> None:
    _active_questions(session, entries)
    sheet.questions.clear()
    session.flush()
    sheet.questions = [
        PracticeSheetQuestion(question_id=entry.question_id, position=index, points=entry.points)
        for index, entry in enumerate(entries)
    ]


def create_practice_sheet(session: Session, payload: PracticeSheetCreate, actor_id: int) -> PracticeSheet:
    _active_questions(session, payload.questions)
    sheet = PracticeSheet(title=payload.title, instructions=payload.instructions, created_by_id=actor_id)
    session.add(sheet)
    session.flush()
    sheet.questions = [
        PracticeSheetQuestion(question_id=entry.question_id, position=index, points=entry.points)
        for index, entry in enumerate(payload.questions)
    ]
    _commit(session)
    session.refresh(sheet)
    return sheet


def update_practice_sheet(session: Session, sheet_id: int, payload: PracticeSheetPatch) -> PracticeSheet:
    sheet = get_practice_sheet(session, sheet_id, lock=True)
    if sheet.status == "finalized":
        raise HTTPException(409, "Finalized practice sheets cannot be edited")
    values = payload.model_dump(exclude_unset=True)
    entries = values.pop("questions", None)
    for name, value in values.items():
        setattr(sheet, name, value)
    if entries is not None:
        _replace_questions(session, sheet, [PracticeSheetQuestionWrite.model_validate(entry) for entry in entries])
    _commit(session)
    session.refresh(sheet)
    return sheet


def delete_practice_sheet(session: Session, sheet_id: int) -> None:
    sheet = get_practice_sheet(session, sheet_id, lock=True)
    if sheet.status == "finalized":
        raise HTTPException(409, "Finalized practice sheets cannot be deleted")
    session.delete(sheet)
    _commit(session)


def _snapshot(question: Question, points: int | None, position: int) -> dict:
    return {
        "question_id": question.id,
        "position": position,
        "points": points,
        "title": question.title,
        "topic": {"slug": question.topic.slug, "name": question.topic.name},
        "difficulty": question.difficulty,
        "response_type": question.response_type,
        "question_text": question.question_text,
        "expected_answer": question.expected_answer,
        "correct_boolean": question.correct_boolean,
        "explanation": question.explanation,
        "options": [
            {"text": option.text, "is_correct": option.is_correct, "position": option.position}
            for option in question.options
        ],
    }


def generate_variants(session: Session, sheet_id: int, payload: VariantGenerate) -> list[PracticeSheetVariant]:
    sheet = get_practice_sheet(session, sheet_id, lock=True)
    if sheet.status == "finalized":
        raise HTTPException(409, "Finalized practice sheets cannot generate variants")
    existing_labels = {variant.label for variant in sheet.variants}
    if existing_labels.intersection(payload.labels):
        raise HTTPException(409, "A requested variant label already exists")
    pool = sorted(sheet.questions, key=lambda entry: (entry.position, entry.id))
    count = payload.question_count if payload.question_count is not None else len(pool)
    if not pool or count > len(pool):
        raise HTTPException(422, "The selected question pool is insufficient for this variant")
    questions = _active_questions(
        session,
        [PracticeSheetQuestionWrite(question_id=entry.question_id, points=entry.points) for entry in pool],
    )
    existing_signatures = {
        tuple(item.get("question_id") for item in variant.question_snapshot.get("questions", []))
        for variant in sheet.variants if isinstance(variant.question_snapshot, dict)
    }
    created: list[PracticeSheetVariant] = []
    for label in payload.labels:
        selected: list[PracticeSheetQuestion] | None = None
        for attempt in range(128):
            shuffled = list(pool)
            Random(f"{payload.seed}:{label}:{attempt}").shuffle(shuffled)
            candidate = shuffled[:count]
            signature = tuple(entry.question_id for entry in candidate)
            if signature not in existing_signatures:
                selected = candidate
                existing_signatures.add(signature)
                break
        if selected is None:
            raise HTTPException(422, "The selected question pool cannot produce enough distinct variants")
        snapshot = {
            "version": 1,
            "generator_version": _GENERATOR_VERSION,
            "seed": payload.seed,
            "questions": [_snapshot(questions[entry.question_id], entry.points, index) for index, entry in enumerate(selected)],
        }
        variant = PracticeSheetVariant(
            label=label, seed=payload.seed, generator_version=_GENERATOR_VERSION, question_snapshot=snapshot,
        )
        sheet.variants.append(variant)
        created.append(variant)
    _commit(session)
    for variant in created:
        session.refresh(variant)
    return created


def finalize_practice_sheet(session: Session, sheet_id: int) -> PracticeSheet:
    sheet = get_practice_sheet(session, sheet_id, lock=True)
    if sheet.status == "finalized":
        raise HTTPException(409, "Practice sheet is already finalized")
    if not sheet.variants:
        raise HTTPException(422, "Generate at least one variant before finalizing")
    sheet.status = "finalized"
    sheet.finalized_at = datetime.now(timezone.utc)
    _commit(session)
    session.refresh(sheet)
    return sheet
