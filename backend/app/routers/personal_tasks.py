from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import student_user
from app.auth_models import User
from app.database import get_session
from app.personal_task_models import PersonalTask
from app.personal_task_schemas import PersonalTaskRead, PersonalTaskWrite


router = APIRouter(prefix="/student/tasks", tags=["Student tasks"])
DB = Annotated[Session, Depends(get_session)]
Student = Annotated[User, Depends(student_user)]
TaskId = Annotated[int, Path(gt=0)]


def _task(session: Session, task_id: int, user_id: int) -> PersonalTask:
    result = session.scalar(
        select(PersonalTask).where(
            PersonalTask.id == task_id, PersonalTask.user_id == user_id
        )
    )
    if result is None:
        raise HTTPException(404, "Task not found")
    return result


def _apply(task: PersonalTask, payload: PersonalTaskWrite) -> None:
    task.title = payload.title
    task.due_date = payload.due_date
    task.completed = payload.completed
    task.completed_at = (
        task.completed_at or datetime.now(timezone.utc) if payload.completed else None
    )


@router.get("", response_model=list[PersonalTaskRead])
def list_tasks(session: DB, user: Student):
    return list(
        session.scalars(
            select(PersonalTask)
            .where(PersonalTask.user_id == user.id)
            .order_by(PersonalTask.completed.asc(), PersonalTask.due_date.is_(None), PersonalTask.due_date.asc(), PersonalTask.id.asc())
        )
    )


@router.post("", response_model=PersonalTaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: PersonalTaskWrite, session: DB, user: Student):
    task = PersonalTask(user_id=user.id)
    _apply(task, payload)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.put("/{task_id}", response_model=PersonalTaskRead)
def update_task(task_id: TaskId, payload: PersonalTaskWrite, session: DB, user: Student):
    task = _task(session, task_id, user.id)
    _apply(task, payload)
    session.commit()
    session.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: TaskId, session: DB, user: Student):
    session.delete(_task(session, task_id, user.id))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
