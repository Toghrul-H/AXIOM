"""Two opt-in development quizzes made only from existing development questions."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_engine
from app.models import Question
from app.quiz_models import Quiz
from app.quiz_schemas import QuizWrite
from app.services.quizzes import save_quiz


def seed():
    with Session(get_engine()) as session:
        questions = {q.title:q.id for q in session.scalars(select(Question))}
        groups = {
            '[DEV] Foundations Quiz': ['Logic implication','Set membership','Symmetric relation','Function image'],
            '[DEV] Mixed DMI Quiz': ['Logic implication','Set membership','Function image','Complex multiplication','Choosing a pair','Degree sum parity'],
        }
        created = 0
        for title,names in groups.items():
            if session.scalar(select(Quiz.id).where(Quiz.title==title)):
                continue
            if any(f'[DEV] {name}' not in questions for name in names):
                raise RuntimeError('Required development questions missing; run app.seed first. No replacement questions were invented.')
            save_quiz(session,QuizWrite(title=title,description='Development/test content only. Not an official ELTE quiz. Written answers are not automatically graded.',status='ACTIVE',
                questions=[{'question_id':questions[f'[DEV] {name}'],'points':1} for name in names]))
            created += 1
        print(f'Created {created} development quizzes; existing matching quizzes unchanged.')

if __name__ == '__main__':
    seed()
