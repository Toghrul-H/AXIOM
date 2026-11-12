from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import manager_user
from app.auth_models import User
from app.database import get_session
from app.exam_schemas import ExamCreate, ExamPatch, ExamRead
from app.document_generation.compiler import compile_pdf
from app.document_generation.exams import ExamDocumentType, render_exam_document
from app.services.exams import create_exam, delete_exam, finalize_exam, get_exam, list_exams, read_exam, update_exam

router = APIRouter(prefix="/exams", tags=["Exams"])
DB = Annotated[Session, Depends(get_session)]
Manager = Annotated[User, Depends(manager_user)]
Id = Annotated[int, Path(gt=0)]


@router.get("", response_model=list[ExamRead])
def exams(session: DB, actor: Manager, offset: Annotated[int, Query(ge=0)] = 0, limit: Annotated[int, Query(ge=1, le=100)] = 20):
    return list_exams(session, offset, limit)


@router.post("", response_model=ExamRead, status_code=status.HTTP_201_CREATED)
def create(payload: ExamCreate, session: DB, actor: Manager):
    return read_exam(create_exam(session, payload, actor.id))


@router.get("/{exam_id}", response_model=ExamRead)
def detail(exam_id: Id, session: DB, actor: Manager):
    return read_exam(get_exam(session, exam_id))


@router.patch("/{exam_id}", response_model=ExamRead)
def update(exam_id: Id, payload: ExamPatch, session: DB, actor: Manager):
    return read_exam(update_exam(session, exam_id, payload))


@router.delete("/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(exam_id: Id, session: DB, actor: Manager):
    delete_exam(session, exam_id)


@router.post("/{exam_id}/finalize", response_model=ExamRead)
def finalize(exam_id: Id, session: DB, actor: Manager):
    return read_exam(finalize_exam(session, exam_id))


@router.get("/{exam_id}/documents/{document_type}/pdf")
def download_document(exam_id: Id, document_type: ExamDocumentType, session: DB, actor: Manager):
    source = render_exam_document(session, exam_id, document_type)
    # Rendering is read-only; never leave an open transaction while compiling.
    session.rollback()
    pdf = compile_pdf(source)
    filename = f"axiom-exam-{exam_id}-{document_type.value}.pdf"
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
    })
