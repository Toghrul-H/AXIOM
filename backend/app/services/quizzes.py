from datetime import datetime, timezone
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models import Question
from app.quiz_models import Quiz, QuizQuestion, QuizAttempt, AttemptAnswer, AttemptOption
from app.quiz_schemas import QuizWrite, ActiveItem, AttemptSummary
from app.schemas import AnswerCheck
from app.services.grading import check_answer


def get_quiz(session: Session, quiz_id: int, lock=False) -> Quiz:
    stmt = select(Quiz).where(Quiz.id == quiz_id)
    if lock:
        stmt = stmt.with_for_update()
    quiz = session.scalar(stmt)
    if quiz is None:
        raise HTTPException(404, 'Quiz not found')
    return quiz


def save_quiz(session: Session, payload: QuizWrite, quiz_id: int | None = None) -> Quiz:
    quiz = get_quiz(session, quiz_id, lock=True) if quiz_id else Quiz()
    ids = [q.question_id for q in payload.questions]
    questions = list(session.scalars(select(Question).where(Question.id.in_(ids))))
    if len(questions) != len(ids):
        raise HTTPException(422, 'Unknown question in quiz')
    if payload.status == 'ACTIVE' and any(not q.is_active for q in questions):
        raise HTTPException(422, 'Active quizzes require active questions')
    quiz.title, quiz.description, quiz.status = payload.title, payload.description, payload.status
    # Explicitly flush removals before reusing composite keys during composition edits.
    quiz.questions = []
    session.add(quiz)
    session.flush()
    quiz.questions = [QuizQuestion(question_id=q.question_id,position=i,points=q.points) for i,q in enumerate(payload.questions)]
    quiz.updated_at = func.now()
    session.commit()
    session.refresh(quiz)
    return quiz


def start_attempt(session: Session, quiz_id: int, identity: int) -> QuizAttempt:
    quiz = get_quiz(session, quiz_id, lock=True)
    if quiz.status != 'ACTIVE' or not quiz.questions:
        raise HTTPException(409, 'Quiz is not available')
    questions = {q.id:q for q in session.scalars(select(Question).where(Question.id.in_([x.question_id for x in quiz.questions])).order_by(Question.id).with_for_update(of=Question))}
    if len(questions) != len(quiz.questions) or any(not q.is_active for q in questions.values()):
        raise HTTPException(409, 'Quiz contains unavailable questions')
    attempt = QuizAttempt(quiz_id=quiz.id,user_id=identity,quiz_title=quiz.title,objective_total=0)
    for entry in quiz.questions:
        q = questions[entry.question_id]
        item = AttemptAnswer(question_id=q.id,position=entry.position,points=entry.points,
            topic_slug=q.topic.slug,
            skill_code=q.skill_type,
            question_text=q.question_text,response_type=q.response_type,expected_answer=q.expected_answer,
            correct_boolean=q.correct_boolean,explanation=q.explanation,
            options=[AttemptOption(text=o.text,is_correct=o.is_correct,position=o.position) for o in q.options])
        attempt.items.append(item)
        if q.response_type != 'FREE_RESPONSE':
            attempt.objective_total += entry.points
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return attempt


def get_attempt(session: Session, attempt_id: UUID, identity: int, lock=False) -> QuizAttempt:
    stmt = select(QuizAttempt).where(QuizAttempt.id == attempt_id, QuizAttempt.user_id == identity)
    if lock:
        stmt = stmt.with_for_update()
    attempt = session.scalar(stmt)
    if attempt is None:
        raise HTTPException(404,'Attempt not found')
    return attempt


def answered(item: AttemptAnswer) -> bool:
    return bool(item.selected_option_ids) or item.boolean_answer is not None or bool(item.free_response)


def save_answer(session: Session, attempt_id: UUID, item_id: int, identity: int, payload: AnswerCheck) -> QuizAttempt:
    attempt = get_attempt(session,attempt_id,identity,lock=True)
    if attempt.status != 'IN_PROGRESS':
        raise HTTPException(409,'Submitted attempts cannot be changed')
    item = next((i for i in attempt.items if i.id == item_id),None)
    if item is None:
        raise HTTPException(404,'Question is not in this attempt')
    kind = item.response_type
    if kind in {'SINGLE_CHOICE','MULTIPLE_SELECT'}:
        if payload.boolean_answer is not None or payload.free_response is not None:
            raise HTTPException(422,'Use selected_option_ids only')
        if kind == 'SINGLE_CHOICE' and len(payload.selected_option_ids) > 1:
            raise HTTPException(422,'Select at most one option')
        if not set(payload.selected_option_ids).issubset({o.id for o in item.options}):
            raise HTTPException(422,'Option does not belong to this attempt question')
    elif kind == 'TRUE_FALSE':
        if payload.selected_option_ids or payload.free_response is not None:
            raise HTTPException(422,'Use boolean_answer only')
    elif payload.selected_option_ids or payload.boolean_answer is not None:
        raise HTTPException(422,'Use free_response only')
    item.selected_option_ids = payload.selected_option_ids
    item.boolean_answer = payload.boolean_answer
    item.free_response = payload.free_response
    session.commit()
    session.refresh(attempt)
    return attempt


def submit_attempt(session: Session, attempt_id: UUID, identity: int) -> QuizAttempt:
    attempt = get_attempt(session,attempt_id,identity,lock=True)
    if attempt.status == 'SUBMITTED':
        return attempt  # Idempotent retry; never regrade a completed attempt.
    score = 0
    for item in attempt.items:
        if item.response_type == 'FREE_RESPONSE':
            continue
        if answered(item):
            feedback = check_answer(item,AnswerCheck(selected_option_ids=item.selected_option_ids,
                boolean_answer=item.boolean_answer,free_response=item.free_response))
            item.is_correct = feedback.is_correct
        else:
            item.is_correct = False
        item.points_awarded = item.points if item.is_correct else 0
        score += item.points_awarded
    attempt.objective_score = score
    attempt.status = 'SUBMITTED'
    attempt.submitted_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(attempt)
    return attempt


def review(attempt: QuizAttempt) -> dict:
    if attempt.status != 'SUBMITTED':
        raise HTTPException(409,'Finish the quiz before reviewing answers')
    result = AttemptSummary.model_validate(attempt).model_dump()
    result.update(correct_count=0,incorrect_count=0,unanswered_objective_count=0,ungraded_count=0,items=[])
    for item in attempt.items:
        objective = item.response_type != 'FREE_RESPONSE'
        result['ungraded_count'] += not objective
        result['correct_count'] += objective and item.is_correct is True
        result['incorrect_count'] += objective and item.is_correct is False
        result['unanswered_objective_count'] += objective and not answered(item)
        result['items'].append(dict(**ActiveItem.model_validate(item).model_dump(),answered=answered(item),
            auto_gradable=objective,is_correct=item.is_correct,points_awarded=item.points_awarded,
            correct_option_ids=[o.id for o in item.options if o.is_correct],correct_boolean=item.correct_boolean,
            expected_answer=item.expected_answer,explanation=item.explanation))
    return result

