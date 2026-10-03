"""Explicit M7 local demo preparation using the existing account/content services."""
import argparse
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.database import get_engine
from app.models import Question, Topic
from app.quiz_models import Quiz
from app.schemas import QuestionCreate
from app.quiz_schemas import QuizWrite
from app.services.questions import save_question, question_input
from app.services.quizzes import save_quiz
from app.scripts.seed_demo_users import configured_accounts, ensure_demo_users

TITLE = 'M7 Manual Grading Demo'
EXAMPLES = [
    ('sets', 'Subset definition', 'SINGLE_CHOICE', 'DEFINITION', 1,
     'Which statement correctly expresses A ⊆ B?',
     {'options': [{'text':'Every element of A is also an element of B.','is_correct':True},
                  {'text':'Every element of B is also an element of A.'},
                  {'text':'A and B have no common elements.'},
                  {'text':'A contains exactly one element.'}]}, None),
    ('binary-relations', 'Equivalence reflexivity', 'TRUE_FALSE', 'DEFINITION', 1,
     'Every equivalence relation is reflexive.', {'correct_boolean':True}, None),
    ('sets', 'Intersection proof', 'FREE_RESPONSE', 'PROOF', 5,
     'Let B ⊆ A and C ⊆ A. Prove that B ∩ C ⊆ A.',
     {'expected_answer':'Let x ∈ B ∩ C. Then x ∈ B and x ∈ C. Since B ⊆ A, x ∈ A. Therefore every element of B ∩ C belongs to A, so B ∩ C ⊆ A.'},
     'The proof uses the definition of intersection and subset.'),
    ('functions', 'Injective and surjective', 'FREE_RESPONSE', 'DEFINITION', 4,
     'Explain the difference between an injective function and a surjective function.',
     {'expected_answer':'A function is injective if distinct inputs cannot map to the same output. A function is surjective if every element of the codomain is the image of at least one element of the domain.'}, None),
]


def ensure_content(session: Session) -> int:
    # Caller owns the transaction and validates local opt-in before opening it.
    topics = dict(session.execute(select(Topic.slug, Topic.id)).all())
    entries = []
    for slug, name, kind, skill, points, prompt, answer, explanation in EXAMPLES:
        title = '[DEV M7] ' + name
        matches = list(session.scalars(select(Question).where(Question.title == title)))
        if len(matches) > 1:
            raise ValueError('Duplicate M7 question titles found; resolve them before seeding.')
        existing = matches[0] if matches else None
        payload = QuestionCreate(topic_id=topics[slug], title=title,
            difficulty='medium' if skill == 'PROOF' else 'easy', response_type=kind,
            skill_type=skill, question_text=prompt, explanation=explanation, **answer)
        if existing:
            old = question_input(existing)
            for option in old['options']:
                option.pop('id', None)
            desired = payload.model_dump()
            for option in desired['options']:
                option.pop('id', None)
            if old == desired:
                entries.append({'question_id':existing.id, 'points':points})
                continue
            # Reuse ordered option IDs so resetting demo text does not churn option identity.
            for index, option in enumerate(payload.options):
                if index < len(existing.options):
                    option.id = existing.options[index].id
        question = save_question(session, payload, existing)
        entries.append({'question_id':question.id, 'points':points})
    matches = list(session.scalars(select(Quiz).where(Quiz.title == TITLE)))
    if len(matches) > 1:
        raise ValueError('Duplicate M7 quiz titles found; resolve them before seeding.')
    quiz = matches[0] if matches else None
    description = 'Local development demo for objective grading and staff review. Not official course assessment.'
    if quiz and quiz.status == 'ACTIVE' and quiz.description == description and [
        {'question_id':q.question_id,'points':q.points} for q in quiz.questions
    ] == entries:
        return quiz.id
    return save_quiz(session, QuizWrite(title=TITLE, description=description,
        status='ACTIVE', questions=entries), quiz.id if quiz else None).id


def seed():
    configured_accounts()  # Existing enable/password/loopback guards; no remote access.
    with get_engine().begin() as connection:
        connection.execute(text('SELECT pg_advisory_xact_lock(184271905)'))
        # Existing services commit their sessions. Savepoints keep this command atomic.
        with Session(connection, join_transaction_mode='create_savepoint') as session:
            ensure_demo_users(session)
            quiz_id = ensure_content(session)
    return quiz_id


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-development', action='store_true', required=True)
    parser.parse_args()
    try:
        quiz_id=seed()
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    print(f'Local demo accounts and M7 quiz #{quiz_id} are ready. Existing attempts are preserved.')


if __name__ == '__main__':
    main()
