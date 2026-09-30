"""Read-only practice analytics from immutable attempt snapshots, never Question."""
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.models import Topic, SkillType
from app.quiz_models import QuizAttempt, AttemptAnswer
from app.progress_schemas import (
    Performance, TopicPerformance, SkillPerformance, Overview, RecentAttempt, ProgressRead,
)

TOPICS = ('logic', 'sets', 'binary-relations', 'functions', 'complex-numbers', 'combinatorics', 'graphs')
SKILLS = ('CALCULATION', 'DEFINITION', 'PROOF', 'THEOREM', 'EXAMPLE', 'APPLICATION', 'CONSTRUCTION', 'CLASSIFICATION')


def counts(item: AttemptAnswer) -> tuple[int, int, int]:
    if item.response_type == 'FREE_RESPONSE':
        answered = bool(item.free_response and item.free_response.strip())
    elif item.response_type == 'TRUE_FALSE':
        answered = item.boolean_answer is not None
    else:
        answered = bool(item.selected_option_ids)
    graded = answered and item.response_type != 'FREE_RESPONSE' and item.is_correct is not None
    return int(answered), int(graded), int(graded and item.is_correct is True)


def add(target: Performance, values: tuple[int, int, int]):
    target.answered_count += values[0]
    target.auto_graded_count += values[1]
    target.correct_count += values[2]
    target.accuracy_percent = (
        round(100 * target.correct_count / target.auto_graded_count, 2)
        if target.auto_graded_count else None
    )


def progress_for(session: Session, user_id: int) -> ProgressRead:
    topic_names = dict(session.execute(select(Topic.slug, Topic.name)).all())
    skill_names = dict(session.execute(select(SkillType.code, SkillType.label)).all())
    topics = {slug: TopicPerformance(slug=slug, name=topic_names[slug]) for slug in TOPICS}
    skills = {code: SkillPerformance(code=code, name=skill_names[code]) for code in SKILLS}
    unknown_topic, unknown_skill, total = Performance(), Performance(), Performance()
    attempts = session.scalars(
        select(QuizAttempt).where(QuizAttempt.user_id == user_id, QuizAttempt.status == 'SUBMITTED')
        .options(selectinload(QuizAttempt.items).raiseload('*'))
        .order_by(QuizAttempt.submitted_at.desc(), QuizAttempt.id.desc())
    ).all()
    recent = []
    for attempt in attempts:
        result = Performance()
        for item in attempt.items:
            values = counts(item)
            for target in (total, result, topics.get(item.topic_slug, unknown_topic), skills.get(item.skill_code, unknown_skill)):
                add(target, values)
        if len(recent) < 10:
            recent.append(RecentAttempt(
                **result.model_dump(), id=attempt.id, quiz_id=attempt.quiz_id,
                quiz_title=attempt.quiz_title, submitted_at=attempt.submitted_at,
                total_question_count=len(attempt.items), objective_score=attempt.objective_score,
                objective_total=attempt.objective_total,
            ))
    return ProgressRead(
        overview=Overview(completed_quizzes=len({a.quiz_id for a in attempts}),
            completed_attempts=len(attempts), questions_answered=total.answered_count,
            auto_graded_questions=total.auto_graded_count, auto_graded_correct=total.correct_count,
            auto_graded_accuracy=total.accuracy_percent),
        topics=list(topics.values()), skills=list(skills.values()),
        unattributed_topic=unknown_topic, unattributed_skill=unknown_skill, recent_attempts=recent,
    )
