from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import student_user
from app.auth_models import User
from app.database import get_session
from app.learning_schemas import LearningSummary, PracticeStart, PracticeTopic
from app.quiz_schemas import ActiveAttempt
from app.services.learning import create_practice_attempt, learning_summary, practice_topics


router = APIRouter(prefix='/student', tags=['Student learning'])
DB = Annotated[Session, Depends(get_session)]
Identity = Annotated[User, Depends(student_user)]


@router.get('/learning/summary', response_model=LearningSummary)
def summary(session: DB, identity: Identity):
    return learning_summary(session, identity.id)


@router.get('/practice/topics', response_model=list[PracticeTopic])
def topics(session: DB, identity: Identity):
    return practice_topics(session, identity.id)


@router.post('/practice/sessions', response_model=ActiveAttempt, status_code=201)
def start_practice(payload: PracticeStart, session: DB, identity: Identity):
    return create_practice_attempt(session, identity.id, payload.topic_slug, payload.question_count)
