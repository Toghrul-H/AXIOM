from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.auth import student_user
from app.auth_models import User
from app.database import get_session
from app.progress_schemas import ProgressRead
from app.services.progress import progress_for

router = APIRouter(tags=['Student progress'])


@router.get('/student/progress/me', response_model=ProgressRead)
def my_progress(session: Annotated[Session, Depends(get_session)],
                user: Annotated[User, Depends(student_user)]):
    return progress_for(session, user.id)
