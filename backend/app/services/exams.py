"""Transactional exam composition and finalization."""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.assessment_models import AssessmentConfiguration
from app.exam_models import Exam, ExamQuestion
from app.exam_schemas import ExamCreate, ExamPatch, ExamQuestionWrite
from app.models import Question


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "Conflicting exam data") from None


def get_exam(session: Session, exam_id: int, *, lock: bool = False) -> Exam:
    statement = select(Exam).where(Exam.id == exam_id)
    if lock:
        statement = statement.with_for_update()
    exam = session.scalar(statement)
    if exam is None:
        raise HTTPException(404, "Exam not found")
    return exam


def read_exam(exam: Exam) -> dict:
    return {
        "id": exam.id,
        "title": exam.title,
        "instructions": exam.instructions,
        "status": exam.status,
        "assessment_configuration_id": exam.assessment_configuration_id,
        "created_by_id": exam.created_by_id,
        "finalized_at": exam.finalized_at,
        "created_at": exam.created_at,
        "updated_at": exam.updated_at,
        "questions": [
            {"question_id": entry.question_id, "points": entry.points, "position": entry.position}
            for entry in exam.questions
        ],
        "snapshot_available": exam.question_snapshot is not None,
    }


def list_exams(session: Session, offset: int, limit: int) -> list[dict]:
    exams = session.scalars(
        select(Exam).order_by(Exam.updated_at.desc(), Exam.id.desc()).offset(offset).limit(limit)
    ).all()
    return [read_exam(exam) for exam in exams]


def _valid_questions(
    session: Session, entries: list[ExamQuestionWrite], *, lock: bool = False
) -> dict[int, Question]:
    ids = [entry.question_id for entry in entries]
    if not ids:
        return {}
    statement = (
        select(Question)
        .where(Question.id.in_(ids))
        .options(selectinload(Question.options), selectinload(Question.topic))
    )
    if lock:
        statement = statement.with_for_update(of=Question)
    rows = session.scalars(statement).all()
    if len(rows) != len(ids):
        raise HTTPException(422, "Unknown question in exam")
    if any(not question.is_active for question in rows):
        raise HTTPException(422, "Exams require active questions")
    return {question.id: question for question in rows}


def _replace_questions(session: Session, exam: Exam, entries: list[ExamQuestionWrite]) -> None:
    _valid_questions(session, entries)
    exam.questions.clear()
    session.flush()
    exam.questions = [
        ExamQuestion(question_id=entry.question_id, position=index, points=entry.points)
        for index, entry in enumerate(entries)
    ]


def _valid_configuration(session: Session, configuration_id: int | None) -> None:
    if configuration_id is not None and session.get(AssessmentConfiguration, configuration_id) is None:
        raise HTTPException(422, "Unknown assessment configuration")


def create_exam(session: Session, payload: ExamCreate, actor_id: int) -> Exam:
    _valid_questions(session, payload.questions)
    _valid_configuration(session, payload.assessment_configuration_id)
    exam = Exam(
        title=payload.title,
        instructions=payload.instructions,
        assessment_configuration_id=payload.assessment_configuration_id,
        created_by_id=actor_id,
    )
    session.add(exam)
    session.flush()
    exam.questions = [
        ExamQuestion(question_id=entry.question_id, position=index, points=entry.points)
        for index, entry in enumerate(payload.questions)
    ]
    _commit(session)
    session.refresh(exam)
    return exam


def update_exam(session: Session, exam_id: int, payload: ExamPatch) -> Exam:
    exam = get_exam(session, exam_id, lock=True)
    if exam.status == "finalized":
        raise HTTPException(409, "Finalized exams cannot be edited")
    values = payload.model_dump(exclude_unset=True)
    entries = values.pop("questions", None)
    if "assessment_configuration_id" in values:
        _valid_configuration(session, values["assessment_configuration_id"])
    for name, value in values.items():
        setattr(exam, name, value)
    if entries is not None:
        _replace_questions(session, exam, [ExamQuestionWrite.model_validate(entry) for entry in entries])
    _commit(session)
    session.refresh(exam)
    return exam


def delete_exam(session: Session, exam_id: int) -> None:
    exam = get_exam(session, exam_id, lock=True)
    if exam.status == "finalized":
        raise HTTPException(409, "Finalized exams cannot be deleted")
    session.delete(exam)
    _commit(session)


def finalize_exam(session: Session, exam_id: int) -> Exam:
    exam = get_exam(session, exam_id, lock=True)
    if exam.status == "finalized":
        raise HTTPException(409, "Exam is already finalized")
    entries = list(exam.questions)
    if not entries:
        raise HTTPException(422, "An exam needs at least one question before finalization")
    questions = _valid_questions(
        session,
        [ExamQuestionWrite(question_id=entry.question_id, points=entry.points) for entry in entries],
        lock=True,
    )
    exam.question_snapshot = {
        "version": 1,
        "title": exam.title,
        "instructions": exam.instructions,
        "questions": [
            {
                "question_id": entry.question_id,
                "position": entry.position,
                "points": entry.points,
                "title": questions[entry.question_id].title,
                "topic": {
                    "slug": questions[entry.question_id].topic.slug,
                    "name": questions[entry.question_id].topic.name,
                },
                "difficulty": questions[entry.question_id].difficulty,
                "response_type": questions[entry.question_id].response_type,
                "question_text": questions[entry.question_id].question_text,
                "expected_answer": questions[entry.question_id].expected_answer,
                "correct_boolean": questions[entry.question_id].correct_boolean,
                "explanation": questions[entry.question_id].explanation,
                "options": [
                    {"text": option.text, "is_correct": option.is_correct, "position": option.position}
                    for option in questions[entry.question_id].options
                ],
            }
            for entry in entries
        ],
    }
    exam.status = "finalized"
    exam.finalized_at = datetime.now(timezone.utc)
    _commit(session)
    session.refresh(exam)
    return exam
