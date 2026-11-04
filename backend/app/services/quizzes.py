from datetime import datetime, timezone
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models import Question, Topic
from app.quiz_models import Quiz, QuizQuestion, QuizAttempt, AttemptAnswer, AttemptOption
from app.quiz_schemas import QuizWrite, ActiveItem, AttemptSummary
from app.schemas import AnswerCheck
from app.services.grading import check_answer


def get_quiz(session: Session, quiz_id: int, lock=False, include_practice=False) -> Quiz:
    stmt = select(Quiz).where(Quiz.id == quiz_id)
    if not include_practice:
        stmt = stmt.where(Quiz.is_practice.is_(False))
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
    return _snapshot_attempt(session, quiz, identity, questions)


def _snapshot_attempt(session: Session, quiz: Quiz, identity: int, questions: dict[int, Question]) -> QuizAttempt:
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


def start_practice_attempt(session: Session, topic_slug: str, question_count: int, identity: int) -> QuizAttempt:
    """Create a private practice composition and snapshot it as an attempt.

    Only active, curated DMI imports are eligible.  A private Quiz preserves
    the existing immutable-attempt architecture without exposing a student's
    selected composition to other students or the staff quiz-management list.
    """
    topic = session.scalar(select(Topic).where(Topic.slug == topic_slug))
    if topic is None:
        raise HTTPException(404, 'Practice topic not found')
    eligible = list(session.scalars(
        select(Question).where(
            Question.topic_id == topic.id,
            Question.is_active.is_(True),
            Question.external_source_id.like('M10A3:%'),
        ).order_by(Question.id).with_for_update(of=Question)
    ))
    if len(eligible) < question_count:
        raise HTTPException(422, 'Not enough available practice questions for this topic')
    seen = set(session.scalars(
        select(AttemptAnswer.question_id).join(QuizAttempt).where(
            QuizAttempt.user_id == identity,
            AttemptAnswer.question_id.is_not(None),
        )
    ))
    unseen = [question for question in eligible if question.id not in seen]
    selected = (unseen + [question for question in eligible if question.id in seen])[:question_count]
    quiz = Quiz(
        title=f'Practice · {topic.name}',
        description=f'Private topic practice: {topic.name}',
        status='INACTIVE',
        is_practice=True,
        practice_owner_id=identity,
        questions=[QuizQuestion(question_id=question.id, position=index, points=1) for index, question in enumerate(selected)],
    )
    session.add(quiz)
    session.flush()
    return _snapshot_attempt(session, quiz, identity, {question.id: question for question in selected})


def get_attempt(session: Session, attempt_id: UUID, identity: int, lock=False) -> QuizAttempt:
    stmt = select(QuizAttempt).where(QuizAttempt.id == attempt_id, QuizAttempt.user_id == identity)
    if lock:
        stmt = stmt.with_for_update()
    attempt = session.scalar(stmt)
    if attempt is None:
        raise HTTPException(404,'Attempt not found')
    return attempt


def attempt_summary(attempt: QuizAttempt) -> dict:
    """A student-safe status summary derived from immutable attempt items."""
    result = AttemptSummary.model_validate(attempt).model_dump()
    manual = [item for item in attempt.items if item.response_type == 'FREE_RESPONSE']
    pending = [item for item in manual if item.manual_points is None]
    graded = [item for item in manual if item.manual_points is not None]
    result.update(
        answered_question_count=sum(answered(item) for item in attempt.items),
        manual_answer_count=len(manual),
        pending_grading_count=len(pending) if attempt.status == 'SUBMITTED' else 0,
        graded_question_count=len(graded),
        grading_status=(
            'NOT_APPLICABLE' if not manual else
            'AWAITING_GRADING' if attempt.status != 'SUBMITTED' or not graded else
            'PARTIALLY_GRADED' if pending else 'GRADED'
        ),
        is_practice=bool(attempt.quiz.is_practice),
    )
    return result


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
    result = attempt_summary(attempt)
    result.update(correct_count=0,incorrect_count=0,unanswered_objective_count=0,ungraded_count=0,items=[])
    for item in attempt.items:
        objective = item.response_type != 'FREE_RESPONSE'
        result['ungraded_count'] += not objective
        result['correct_count'] += objective and item.is_correct is True
        result['incorrect_count'] += objective and item.is_correct is False
        result['unanswered_objective_count'] += objective and not answered(item)
        result['items'].append(dict(**ActiveItem.model_validate(item).model_dump(),answered=answered(item),
            auto_gradable=objective,is_correct=item.is_correct,points_awarded=item.points_awarded,
            manual_grading_status='NOT_APPLICABLE' if objective else ('PENDING' if item.manual_points is None else 'COMPLETED'),
            manual_points=item.manual_points,manual_feedback=item.manual_feedback,graded_at=item.graded_at,
            correct_option_ids=[o.id for o in item.options if o.is_correct],correct_boolean=item.correct_boolean,
            expected_answer=item.expected_answer,explanation=item.explanation))
    return result

