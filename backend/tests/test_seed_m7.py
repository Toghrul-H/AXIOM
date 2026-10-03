import os
import secrets
import pytest
from unittest.mock import patch
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.database import get_engine
from app.models import Question
from app.quiz_models import Quiz, QuizQuestion
from app.seed_m7 import ensure_content, TITLE, EXAMPLES, seed

@pytest.mark.integration
@pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS') != '1',reason='Set RUN_POSTGRES_TESTS=1')
def test_m7_content_idempotent_and_update():
    from app.config import get_settings
    assert get_settings().database_host.lower() in {'localhost','127.0.0.1','::1'}
    with get_engine().connect() as connection:
        transaction=connection.begin()
        try:
            with Session(connection,join_transaction_mode='create_savepoint') as session:
                before=session.scalar(select(func.count()).select_from(Question))
                quiz_id=ensure_content(session)
                quiz=session.get(Quiz,quiz_id)
                ids=[q.question_id for q in quiz.questions]
                assert [q.points for q in quiz.questions]==[1,1,5,4]
                count=session.scalar(select(func.count()).select_from(Question))
                assert ensure_content(session)==quiz_id
                assert session.scalar(select(func.count()).select_from(Question))==count
                assert session.scalar(select(func.count()).select_from(Quiz).where(Quiz.title==TITLE))==1
                assert session.scalar(select(func.count()).select_from(QuizQuestion).where(QuizQuestion.quiz_id==quiz_id))==4
                question=session.get(Question,ids[0]); question.question_text='Edited demo';session.commit()
                assert ensure_content(session)==quiz_id
                session.refresh(question)
                assert question.question_text==EXAMPLES[0][5]
                assert session.scalar(select(func.count()).select_from(Question))==count
        finally:
            transaction.rollback()


def test_m7_seed_checks_configuration_before_database():
    with patch('app.seed_m7.configured_accounts',side_effect=ValueError('Disabled')), patch('app.seed_m7.get_engine') as engine:
        with pytest.raises(ValueError): seed()
        engine.assert_not_called()

@pytest.mark.integration
@pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS') != '1',reason='Set RUN_POSTGRES_TESTS=1')
def test_m7_seeded_workflow(accounts,monkeypatch):
    from uuid import uuid4
    from sqlalchemy import delete
    from fastapi.testclient import TestClient
    from app.main import app
    from app.quiz_models import QuizAttempt
    import app.seed_m7 as demo
    suffix=uuid4().hex
    monkeypatch.setattr(demo,'TITLE','Test M7 '+suffix)
    monkeypatch.setattr(demo,'EXAMPLES',[(slug,name+' '+suffix,*rest) for slug,name,*rest in EXAMPLES])
    _,student=accounts()
    _,lecturer=accounts('LECTURER')
    _,demonstrator=accounts('DEMONSTRATOR')
    with Session(get_engine()) as session:
        quiz_id=demo.ensure_content(session)
        question_ids=[q.question_id for q in session.get(Quiz,quiz_id).questions]
    try:
        with TestClient(app) as client:
            r=client.post(f'/student/quizzes/{quiz_id}/attempts',headers=student)
            assert r.status_code==201,r.text
            attempt=r.json();base=f"/student/attempts/{attempt['id']}"
            answers=[{'selected_option_ids':[attempt['items'][0]['options'][0]['id']]},{'boolean_answer':True},{'free_response':'Take x in B intersection C. Then x is in B, hence in A.'},{'free_response':'Injective: distinct inputs have distinct outputs. Surjective: every codomain element has a preimage.'}]
            for item,answer in zip(attempt['items'],answers):
                assert client.put(base+f"/answers/{item['id']}",headers=student,json=answer).status_code==200
            review=client.post(base+'/submit',headers=student).json()
            assert review['objective_score']==2 and review['objective_total']==2
            assert all(i['manual_grading_status']=='PENDING' for i in review['items'][2:])
            progress=client.get('/student/progress/me',headers=student).json()
            staffbase=f"/grading/attempts/{attempt['id']}"
            for headers,item,points in [(lecturer,attempt['items'][2],4),(demonstrator,attempt['items'][3],3)]:
                queue=client.get('/grading/attempts?limit=100',headers=headers)
                assert queue.status_code==200
                assert any(a['attempt_id']==attempt['id'] for a in queue.json()['items'])
                assert client.get(staffbase,headers=headers).status_code==200
                assert client.put(staffbase+f"/answers/{item['id']}",headers=headers,json={'points':points,'feedback':'Local integration feedback'}).status_code==200
            latest=client.get(base+'/review',headers=student).json()
            assert [i['manual_points'] for i in latest['items'][2:]]==[4,3]
            assert all(i['manual_feedback']=='Local integration feedback' for i in latest['items'][2:])
            assert latest['objective_score']==review['objective_score']
            assert client.get('/student/progress/me',headers=student).json()==progress
    finally:
        with Session(get_engine()) as session:
            session.execute(delete(QuizAttempt).where(QuizAttempt.quiz_id==quiz_id))
            session.execute(delete(Quiz).where(Quiz.id==quiz_id))
            session.execute(delete(Question).where(Question.id.in_(question_ids)))
            session.commit()
