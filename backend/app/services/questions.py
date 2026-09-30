from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models import AssessmentSuitability, ProblemSet, Question, QuestionOption, SkillType, Topic
from app.schemas import QuestionCreate


def find_question(session: Session, question_id: int) -> Question:
    question = session.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return question


def question_input(question: Question) -> dict:
    return {
        "topic_id": question.topic_id, "title": question.title,
        "difficulty": question.difficulty, "response_type": question.response_type,
        "skill_type": question.skill_type, "question_text": question.question_text,
        "expected_answer": question.expected_answer, "correct_boolean": question.correct_boolean,
        "explanation": question.explanation, "is_active": question.is_active,
        "options": [{"id": o.id, "text": o.text, "is_correct": o.is_correct} for o in question.options],
        "problem_set_ids": [p.id for p in question.problem_sets],
        "assessment_suitability_codes": [tag.code for tag in question.assessment_suitabilities],
    }


def save_question(session: Session, payload: QuestionCreate, question: Question | None = None) -> Question:
    topic = session.get(Topic, payload.topic_id)
    if topic is None:
        raise HTTPException(status_code=422, detail="Unknown topic_id")
    if session.get(SkillType, payload.skill_type) is None:
        raise HTTPException(status_code=422, detail="Unknown skill_type")
    problem_sets = list(session.scalars(select(ProblemSet).where(ProblemSet.id.in_(payload.problem_set_ids))))
    if len(problem_sets) != len(payload.problem_set_ids):
        raise HTTPException(status_code=422, detail="Unknown problem set association")
    tags = list(session.scalars(select(AssessmentSuitability).where(AssessmentSuitability.code.in_(payload.assessment_suitability_codes))))
    if len(tags) != len(payload.assessment_suitability_codes):
        raise HTTPException(status_code=422, detail="Unknown assessment suitability association")
    existing_options = {o.id: o for o in question.options} if question else {}
    for option in payload.options:
        if option.id is not None and option.id not in existing_options:
            raise HTTPException(status_code=422, detail="Option ID does not belong to this question")
    question = question or Question()
    for field in ("title", "difficulty", "response_type", "skill_type", "question_text", "expected_answer", "correct_boolean", "explanation", "is_active"):
        setattr(question, field, getattr(payload, field))
    question.topic = topic
    question.problem_sets = problem_sets
    question.assessment_suitabilities = tags
    options = []
    for position, data in enumerate(payload.options):
        option = existing_options[data.id] if data.id is not None else QuestionOption()
        option.text, option.is_correct, option.position = data.text, data.is_correct, position
        options.append(option)
    question.options = options
    question.updated_at = func.now()
    session.add(question)
    session.commit()
    session.refresh(question)
    return question
