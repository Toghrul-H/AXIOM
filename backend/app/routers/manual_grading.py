from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.auth import staff_user
from app.auth_models import User
from app.database import get_session
from app.quiz_models import QuizAttempt, AttemptAnswer
from app.services.quizzes import review
from app.manual_grading_schemas import ManualGradeWrite, GradingQueue, GradingAttempt

router = APIRouter(prefix='/grading/attempts', tags=['Manual grading'])
DB = Annotated[Session, Depends(get_session)]
Staff = Annotated[User, Depends(staff_user)]


@router.get('', response_model=GradingQueue)
def queue(session: DB, actor: Staff,
          status: Literal['pending', 'completed', 'all'] = 'pending',
          offset: Annotated[int, Query(ge=0)] = 0,
          limit: Annotated[int, Query(ge=1, le=100)] = 20):
    counts = select(
        AttemptAnswer.quiz_attempt_id.label('attempt_id'),
        func.count().label('manual_count'),
        func.count().filter(AttemptAnswer.manual_points.is_(None)).label('pending'),
    ).where(AttemptAnswer.response_type == 'FREE_RESPONSE').group_by(AttemptAnswer.quiz_attempt_id).subquery()
    stmt = select(QuizAttempt.id, QuizAttempt.user_id, User.email, QuizAttempt.quiz_id,
                  QuizAttempt.quiz_title, QuizAttempt.submitted_at, counts.c.manual_count, counts.c.pending
                  ).join(counts, counts.c.attempt_id == QuizAttempt.id).join(User, User.id == QuizAttempt.user_id
                  ).where(QuizAttempt.status == 'SUBMITTED')
    if status == 'pending':
        stmt = stmt.where(counts.c.pending > 0)
    elif status == 'completed':
        stmt = stmt.where(counts.c.pending == 0)
    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = session.execute(stmt.order_by(QuizAttempt.submitted_at, QuizAttempt.id).offset(offset).limit(limit)).all()
    return dict(total=total, offset=offset, limit=limit, items=[dict(
        attempt_id=r.id, student=dict(id=r.user_id, email=r.email), quiz_id=r.quiz_id,
        quiz_title=r.quiz_title, submitted_at=r.submitted_at, manual_answer_count=r.manual_count,
        pending_count=r.pending, grading_status='PENDING' if r.pending else 'COMPLETED',
    ) for r in rows])


def submitted_attempt(session: Session, attempt_id: UUID, lock=False):
    stmt = select(QuizAttempt).where(QuizAttempt.id == attempt_id)
    if lock:
        stmt = stmt.with_for_update()
    attempt = session.scalar(stmt)
    if attempt is None:
        raise HTTPException(404, 'Attempt not found')
    if attempt.status != 'SUBMITTED':
        raise HTTPException(409, 'Only submitted attempts may be manually graded')
    if not any(i.response_type == 'FREE_RESPONSE' for i in attempt.items):
        raise HTTPException(409, 'This attempt has no manually gradable answers')
    return attempt


def staff_review(session: Session, attempt: QuizAttempt):
    result = review(attempt)
    user = session.get(User, attempt.user_id)
    result['student'] = dict(id=user.id, email=user.email)
    for data, item in zip(result['items'], attempt.items):
        data['graded_by_id'] = item.graded_by_id
    return result


@router.get('/{attempt_id}', response_model=GradingAttempt)
def inspect_attempt(attempt_id: UUID, session: DB, actor: Staff):
    return staff_review(session, submitted_attempt(session, attempt_id))


@router.put('/{attempt_id}/answers/{answer_id}', response_model=GradingAttempt)
def grade(attempt_id: UUID, answer_id: Annotated[int, Path(gt=0)], payload: ManualGradeWrite,
          session: DB, actor: Staff):
    # Serialize grade updates per attempt, and refresh staff permissions under a lock.
    session.refresh(actor, with_for_update=True)
    if not actor.is_active or actor.role not in {'DEMONSTRATOR', 'LECTURER', 'ADMIN'}:
        raise HTTPException(403, 'Staff grading permission required')
    attempt = submitted_attempt(session, attempt_id, lock=True)
    item = next((i for i in attempt.items if i.id == answer_id), None)
    if item is None:
        raise HTTPException(404, 'Answer does not belong to this attempt')
    if item.response_type != 'FREE_RESPONSE':
        raise HTTPException(422, 'Objective answers cannot be manually graded')
    if payload.points > item.points:
        raise HTTPException(422, 'Points exceed the historical maximum')
    if not (item.free_response or '').strip() and payload.points != 0:
        raise HTTPException(422, 'Unanswered written responses can receive only zero points')
    item.manual_points = payload.points
    item.manual_feedback = payload.feedback
    item.graded_by_id = actor.id
    item.graded_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(attempt)
    return staff_review(session, attempt)
