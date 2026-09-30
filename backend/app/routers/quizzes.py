from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Header, Query, Path, Response
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.database import get_session
from app.auth import staff_user, student_user
from app.auth_models import User
from app.models import Question
from app.quiz_models import Quiz, QuizQuestion, QuizAttempt
from app.quiz_schemas import QuizWrite, QuizStaffRead, QuizSummary, AttemptSummary, ActiveAttempt, AttemptReview
from app.schemas import AnswerCheck
from app.services.quizzes import get_quiz, save_quiz, start_attempt, get_attempt, save_answer, submit_attempt, review

router = APIRouter(tags=['Quizzes'])
DB = Annotated[Session,Depends(get_session)]
Identity = Annotated[User,Depends(student_user)]
Id = Annotated[int,Path(gt=0)]
Limit = Annotated[int,Query(ge=1,le=100)]
Offset = Annotated[int,Query(ge=0)]

@router.get('/quizzes',dependencies=[Depends(staff_user)],response_model=list[QuizStaffRead])
def staff_quizzes(session: DB,limit: Limit=50,offset: Offset=0):
    return list(session.scalars(select(Quiz).order_by(Quiz.id).offset(offset).limit(limit)))

@router.post('/quizzes',dependencies=[Depends(staff_user)],response_model=QuizStaffRead,status_code=201)
def create_quiz(payload: QuizWrite,session: DB):
    return save_quiz(session,payload)

@router.get('/quizzes/{quiz_id}',dependencies=[Depends(staff_user)],response_model=QuizStaffRead)
def staff_quiz(quiz_id: Id,session: DB):
    return get_quiz(session,quiz_id)

@router.put('/quizzes/{quiz_id}',dependencies=[Depends(staff_user)],response_model=QuizStaffRead)
def update_quiz(quiz_id: Id,payload: QuizWrite,session: DB):
    return save_quiz(session,payload,quiz_id)

@router.get('/student/quizzes',response_model=list[QuizSummary])
def student_quizzes(session: DB,identity: Identity,limit: Limit=50,offset: Offset=0):
    quizzes = list(session.scalars(select(Quiz).where(Quiz.status=='ACTIVE').order_by(Quiz.id).offset(offset).limit(limit)))
    result = []
    for q in quizzes:
        questions = list(session.scalars(select(Question).where(Question.id.in_([e.question_id for e in q.questions]))))
        if not questions or any(not x.is_active for x in questions):
            continue
        kinds = {x.id:x.response_type for x in questions}
        result.append(dict(id=q.id,title=q.title,description=q.description,status=q.status,
            question_count=len(q.questions),total_points=sum(e.points for e in q.questions),
            objective_points=sum(e.points for e in q.questions if kinds[e.question_id]!='FREE_RESPONSE')))
    return result

@router.post('/student/quizzes/{quiz_id}/attempts',response_model=ActiveAttempt,status_code=201)
def start(quiz_id: Id,session: DB,identity: Identity,response: Response):
    attempt = start_attempt(session,quiz_id,identity.id)
    response.headers['Location'] = f'/student/attempts/{attempt.id}'
    return attempt

@router.get('/student/attempts',response_model=list[AttemptSummary])
def history(session: DB,identity: Identity,limit: Limit=50,offset: Offset=0):
    return list(session.scalars(select(QuizAttempt).where(QuizAttempt.user_id==identity.id)
        .order_by(QuizAttempt.started_at.desc(),QuizAttempt.id).offset(offset).limit(limit)))

@router.get('/student/attempts/{attempt_id}',response_model=ActiveAttempt)
def resume(attempt_id: UUID,session: DB,identity: Identity):
    return get_attempt(session,attempt_id,identity.id)

@router.put('/student/attempts/{attempt_id}/answers/{item_id}',response_model=ActiveAttempt)
def answer(attempt_id: UUID,item_id: Id,payload: AnswerCheck,session: DB,identity: Identity):
    return save_answer(session,attempt_id,item_id,identity.id,payload)

@router.post('/student/attempts/{attempt_id}/submit',response_model=AttemptReview)
def submit(attempt_id: UUID,session: DB,identity: Identity):
    return review(submit_attempt(session,attempt_id,identity.id))

@router.get('/student/attempts/{attempt_id}/review',response_model=AttemptReview)
def get_review(attempt_id: UUID,session: DB,identity: Identity):
    return review(get_attempt(session,attempt_id,identity.id))

