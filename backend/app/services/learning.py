"""Student-only practice discovery and aggregate learning status.

The data is calculated from immutable attempt snapshots.  It deliberately does
not re-grade free-response work or expose answer/reference content.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.learning_schemas import ContinueLearning, LearningOverview, LearningSummary, PracticeTopic
from app.models import Question, Topic
from app.quiz_models import AttemptAnswer, QuizAttempt
from app.services.quizzes import answered, start_practice_attempt


PRACTICE_TOPIC_SLUGS = (
    'logic', 'sets', 'binary-relations', 'functions',
    'complex-numbers', 'combinatorics', 'graphs',
)


def _topic_rows(session: Session, user_id: int) -> list[PracticeTopic]:
    topics = list(session.scalars(
        select(Topic).where(Topic.slug.in_(PRACTICE_TOPIC_SLUGS)).order_by(Topic.sort_order, Topic.id)
    ))
    topic_by_slug = {topic.slug: topic for topic in topics}
    available = dict(session.execute(
        select(Topic.slug, func.count(Question.id)).join(Question).where(
            Question.is_active.is_(True), Question.external_source_id.like('M10A3:%'),
        ).group_by(Topic.slug)
    ).all())
    attempts = session.scalars(
        select(QuizAttempt).where(QuizAttempt.user_id == user_id)
        .options(selectinload(QuizAttempt.items).raiseload('*'))
    ).all()
    values = {slug: {
        'question_ids': set(), 'submitted_answer_count': 0, 'pending_grading_count': 0,
        'graded_question_count': 0, 'manual_points_awarded': 0, 'manual_points_possible': 0,
    } for slug in PRACTICE_TOPIC_SLUGS}
    for attempt in attempts:
        for item in attempt.items:
            data = values.get(item.topic_slug)
            if data is None:
                continue
            if answered(item) and item.question_id is not None:
                data['question_ids'].add(item.question_id)
            if attempt.status != 'SUBMITTED' or item.response_type != 'FREE_RESPONSE':
                continue
            if answered(item):
                data['submitted_answer_count'] += 1
            if item.manual_points is None:
                data['pending_grading_count'] += 1
            else:
                data['graded_question_count'] += 1
                data['manual_points_awarded'] += item.manual_points
                data['manual_points_possible'] += item.points
    rows = []
    for slug in PRACTICE_TOPIC_SLUGS:
        topic = topic_by_slug.get(slug)
        if topic is None:
            continue
        data = values[slug]
        possible = data['manual_points_possible']
        rows.append(PracticeTopic(
            id=topic.id, slug=slug, name=topic.name,
            available_question_count=available.get(slug, 0),
            attempted_question_count=len(data['question_ids']),
            submitted_answer_count=data['submitted_answer_count'],
            pending_grading_count=data['pending_grading_count'],
            graded_question_count=data['graded_question_count'],
            manual_points_awarded=data['manual_points_awarded'],
            manual_points_possible=possible,
            graded_score_percent=round(100 * data['manual_points_awarded'] / possible, 2) if possible else None,
        ))
    return rows


def practice_topics(session: Session, user_id: int) -> list[PracticeTopic]:
    return _topic_rows(session, user_id)


def learning_summary(session: Session, user_id: int) -> LearningSummary:
    attempts = list(session.scalars(
        select(QuizAttempt).where(QuizAttempt.user_id == user_id)
        .options(selectinload(QuizAttempt.items).raiseload('*'))
        .order_by(QuizAttempt.started_at.desc(), QuizAttempt.id.desc())
    ))
    topics = _topic_rows(session, user_id)
    attempted_ids = set()
    pending = graded = awarded = possible = 0
    for attempt in attempts:
        for item in attempt.items:
            if answered(item) and item.question_id is not None:
                attempted_ids.add(item.question_id)
            if attempt.status == 'SUBMITTED' and item.response_type == 'FREE_RESPONSE':
                if item.manual_points is None:
                    pending += 1
                else:
                    graded += 1
                    awarded += item.manual_points
                    possible += item.points
    in_progress = [attempt for attempt in attempts if attempt.status == 'IN_PROGRESS']
    if in_progress:
        next_step = ContinueLearning(
            kind='RESUME_ATTEMPT', title=f'Resume {in_progress[0].quiz_title}',
            description='Continue your saved answers before submitting.', attempt_id=in_progress[0].id,
        )
    else:
        available = [topic for topic in topics if topic.available_question_count]
        candidate = min(available, key=lambda topic: (topic.attempted_question_count, topic.name)) if available else None
        next_step = ContinueLearning(
            kind='START_PRACTICE' if candidate else 'BROWSE_PRACTICE',
            title=f'Practice {candidate.name}' if candidate else 'Browse practice',
            description=(
                'Start with a topic that has available questions.' if candidate
                else 'No curated practice questions are available yet.'
            ),
            topic_slug=candidate.slug if candidate else None,
        )
    return LearningSummary(
        overview=LearningOverview(
            total_attempted_questions=len(attempted_ids),
            completed_practice_sessions=sum(attempt.status == 'SUBMITTED' for attempt in attempts),
            in_progress_sessions=len(in_progress), pending_grading_count=pending,
            graded_question_count=graded, manual_points_awarded=awarded,
            manual_points_possible=possible,
            graded_score_percent=round(100 * awarded / possible, 2) if possible else None,
        ),
        topics=topics, continue_learning=next_step,
    )


def create_practice_attempt(session: Session, user_id: int, topic_slug: str, question_count: int):
    return start_practice_attempt(session, topic_slug, question_count, user_id)
