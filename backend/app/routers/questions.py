from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from app.database import get_session
from app.models import AssessmentSuitability, ProblemSet, Question, Topic
from app.schemas import AnswerCheck, AnswerFeedback, Difficulty, QuestionCreate, QuestionPage, QuestionPatch, QuestionRead, ResponseKind
from app.services.grading import check_answer
from app.services.questions import find_question, question_input, save_question

from app.auth import staff_user
router = APIRouter(prefix="/questions", tags=["Questions"], dependencies=[Depends(staff_user)])
DatabaseSession = Annotated[Session, Depends(get_session)]
QuestionId = Annotated[int, Path(gt=0)]


@router.post("", response_model=QuestionRead, status_code=status.HTTP_201_CREATED)
def create_question(payload: QuestionCreate, session: DatabaseSession, response: Response) -> Question:
    question = save_question(session, payload)
    response.headers["Location"] = f"/questions/{question.id}"
    return question


@router.get("", response_model=QuestionPage)
def list_questions(
    session: DatabaseSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    topic_id: Annotated[int | None, Query(gt=0)] = None,
    include_descendants: bool = True,
    problem_set_id: Annotated[int | None, Query(gt=0)] = None,
    difficulty: Difficulty | None = None,
    response_type: ResponseKind | None = None,
    skill_type: Annotated[str | None, Query(max_length=40)] = None,
    assessment_suitability: Annotated[str | None, Query(max_length=40)] = None,
    is_active: bool | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> dict:
    filters = []
    if topic_id is not None:
        if include_descendants:
            descendants = select(Topic.id).where(Topic.id == topic_id).cte("descendants", recursive=True)
            descendants = descendants.union(select(Topic.id).where(Topic.parent_id == descendants.c.id))
            filters.append(Question.topic_id.in_(select(descendants.c.id)))
        else:
            filters.append(Question.topic_id == topic_id)
    if problem_set_id is not None:
        filters.append(Question.problem_sets.any(ProblemSet.id == problem_set_id))
    if assessment_suitability is not None:
        filters.append(Question.assessment_suitabilities.any(AssessmentSuitability.code == assessment_suitability))
    for field, value in ((Question.difficulty, difficulty), (Question.response_type, response_type), (Question.skill_type, skill_type), (Question.is_active, is_active)):
        if value is not None:
            filters.append(field == value)
    if q and q.strip():
        filters.append(or_(Question.question_text.icontains(q.strip(), autoescape=True), Question.title.icontains(q.strip(), autoescape=True)))
    total = session.scalar(select(func.count()).select_from(Question).where(*filters))
    items = list(session.scalars(select(Question).where(*filters).order_by(Question.id).offset(offset).limit(limit)))
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/{question_id}", response_model=QuestionRead)
def get_question(question_id: QuestionId, session: DatabaseSession) -> Question:
    return find_question(session, question_id)


@router.patch("/{question_id}", response_model=QuestionRead)
def update_question(question_id: QuestionId, payload: QuestionPatch, session: DatabaseSession) -> Question:
    question = find_question(session, question_id)
    merged = question_input(question)
    merged.update(payload.model_dump(exclude_unset=True))
    try:
        validated = QuestionCreate.model_validate(merged)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_context=False, include_input=False)) from None
    return save_question(session, validated, question)


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(question_id: QuestionId, session: DatabaseSession) -> Response:
    session.delete(find_question(session, question_id))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{question_id}/check", response_model=AnswerFeedback)
def check_question_answer(question_id: QuestionId, payload: AnswerCheck, session: DatabaseSession) -> AnswerFeedback:
    return check_answer(find_question(session, question_id), payload)
