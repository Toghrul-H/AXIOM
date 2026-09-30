from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_session
from app.models import AssessmentSuitability, ProblemSet, ResponseType, SkillType, Topic
from app.schemas import QuestionMetadata

from app.auth import get_current_user
router = APIRouter(tags=["Course structure"], dependencies=[Depends(get_current_user)])


@router.get("/question-metadata", response_model=QuestionMetadata)
def question_metadata(session: Annotated[Session, Depends(get_session)]) -> dict:
    return {
        "topics": list(session.scalars(select(Topic).order_by(Topic.sort_order, Topic.id))),
        "response_types": list(session.scalars(select(ResponseType).order_by(ResponseType.sort_order, ResponseType.code))),
        "skill_types": list(session.scalars(select(SkillType).order_by(SkillType.sort_order, SkillType.code))),
        "problem_sets": list(session.scalars(select(ProblemSet).order_by(ProblemSet.sort_order, ProblemSet.id))),
        "assessment_suitabilities": list(session.scalars(select(AssessmentSuitability).order_by(AssessmentSuitability.sort_order, AssessmentSuitability.code))),
    }
