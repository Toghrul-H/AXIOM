from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import manager_user
from app.auth_models import User
from app.database import get_session
from app.document_generation.compiler import compile_pdf
from app.document_generation.practice_sheets import PracticeSheetDocumentType, render_practice_sheet_document
from app.practice_sheet_schemas import PracticeSheetCreate, PracticeSheetPatch, PracticeSheetRead, PracticeSheetVariantRead, VariantGenerate
from app.services.practice_sheets import (
    create_practice_sheet, delete_practice_sheet, finalize_practice_sheet, generate_variants,
    get_practice_sheet, list_practice_sheets, read_practice_sheet, update_practice_sheet,
)

router = APIRouter(prefix="/practice-sheets", tags=["Practice sheets"])
DB = Annotated[Session, Depends(get_session)]
Manager = Annotated[User, Depends(manager_user)]
Id = Annotated[int, Path(gt=0)]
VariantId = Annotated[int, Path(gt=0)]


@router.get("", response_model=list[PracticeSheetRead])
def sheets(session: DB, actor: Manager, offset: Annotated[int, Query(ge=0)] = 0, limit: Annotated[int, Query(ge=1, le=100)] = 20):
    return list_practice_sheets(session, offset, limit)


@router.post("", response_model=PracticeSheetRead, status_code=status.HTTP_201_CREATED)
def create(payload: PracticeSheetCreate, session: DB, actor: Manager):
    return read_practice_sheet(create_practice_sheet(session, payload, actor.id))


@router.get("/{sheet_id}", response_model=PracticeSheetRead)
def detail(sheet_id: Id, session: DB, actor: Manager):
    return read_practice_sheet(get_practice_sheet(session, sheet_id))


@router.patch("/{sheet_id}", response_model=PracticeSheetRead)
def update(sheet_id: Id, payload: PracticeSheetPatch, session: DB, actor: Manager):
    return read_practice_sheet(update_practice_sheet(session, sheet_id, payload))


@router.delete("/{sheet_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(sheet_id: Id, session: DB, actor: Manager):
    delete_practice_sheet(session, sheet_id)


@router.get("/{sheet_id}/variants", response_model=list[PracticeSheetVariantRead])
def variants(sheet_id: Id, session: DB, actor: Manager):
    return read_practice_sheet(get_practice_sheet(session, sheet_id))["variants"]


@router.post("/{sheet_id}/variants", response_model=list[PracticeSheetVariantRead], status_code=status.HTTP_201_CREATED)
def create_variants(sheet_id: Id, payload: VariantGenerate, session: DB, actor: Manager):
    return [
        {**{"id": item.id, "label": item.label, "seed": item.seed, "generator_version": item.generator_version, "generated_at": item.generated_at},
         "question_count": len(item.question_snapshot["questions"])}
        for item in generate_variants(session, sheet_id, payload)
    ]


@router.get("/{sheet_id}/variants/{variant_id}/documents/{document_type}/pdf")
def download_document(
    sheet_id: Id, variant_id: VariantId, document_type: PracticeSheetDocumentType, session: DB, actor: Manager
):
    source = render_practice_sheet_document(session, sheet_id, variant_id, document_type)
    # Rendering reads only immutable snapshots; release this transaction before compilation.
    session.rollback()
    pdf = compile_pdf(source)
    filename = f"axiom-practice-sheet-{sheet_id}-{variant_id}-{document_type.value}.pdf"
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
    })


@router.post("/{sheet_id}/finalize", response_model=PracticeSheetRead)
def finalize(sheet_id: Id, session: DB, actor: Manager):
    return read_practice_sheet(finalize_practice_sheet(session, sheet_id))
