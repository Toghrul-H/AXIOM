import os
from uuid import UUID, uuid4
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateSchema, DropSchema
from alembic import command
from alembic.config import Config
from app.main import app
from app.database import get_engine
from app.quiz_models import AttemptAnswer
from test_quizzes import setup, start

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS') != '1', reason='Set RUN_POSTGRES_TESTS=1')]
URL='/grading/attempts'


def submitted(c,h,quiz,blank=False):
    a=start(c,h,quiz)
    if not blank:
        assert c.put(f"/student/attempts/{a['id']}/answers/{a['items'][3]['id']}",headers=h,json={'free_response':'My proof'}).status_code==200
    assert c.post(f"/student/attempts/{a['id']}/submit",headers=h).status_code==200
    return a


@pytest.mark.parametrize('role',['DEMONSTRATOR','LECTURER','ADMIN'])
def test_grading_lifecycle(setup,accounts,role):
    c,h,questions,create=setup
    staff,headers=accounts(role)
    quiz=create()
    a=submitted(c,h,quiz)
    base=f"{URL}/{a['id']}"
    endpoint=base+f"/answers/{a['items'][3]['id']}"
    progress=c.get('/student/progress/me',headers=h).json()
    rows=c.get(URL+'?limit=100',headers=headers).json()['items']
    row=next(x for x in rows if x['attempt_id']==a['id'])
    assert row['pending_count']==1 and row['manual_answer_count']==1
    assert set(row['student'])=={'id','email'}
    assert c.get(base,headers=headers).json()['items'][3]['manual_grading_status']=='PENDING'
    # Alter/delete live bank content: all grading limits and references stay historical.
    assert c.patch(f"/questions/{questions[3]['id']}",json={'expected_answer':'New reference','question_text':'Changed bank'}).status_code==200
    assert c.delete(f"/questions/{questions[3]['id']}").status_code==204
    result=c.put(endpoint,headers=headers,json={'points':3,'feedback':'  Good reasoning  '})
    assert result.status_code==200,result.text
    item=result.json()['items'][3]
    assert item['manual_points']==3 and item['manual_feedback']=='Good reasoning'
    assert item['graded_by_id']==staff['id'] and item['graded_at']
    assert item['expected_answer']=='Reference proof' and item['points']==4
    with Session(get_engine()) as s:
        stored=s.get(AttemptAnswer,item['id'])
        assert stored.manual_points==3 and stored.manual_feedback=='Good reasoning'
        assert stored.graded_by_id==staff['id'] and stored.graded_at
        assert stored.is_correct is None and stored.points_awarded is None
    review=c.get(f"/student/attempts/{a['id']}/review",headers=h).json()
    assert review['items'][3]['manual_grading_status']=='COMPLETED'
    assert review['items'][3]['manual_points']==3
    assert 'graded_by_id' not in review['items'][3] and 'student' not in review
    assert c.get('/student/progress/me',headers=h).json()==progress
    assert not any(x['attempt_id']==a['id'] for x in c.get(URL+'?limit=100',headers=headers).json()['items'])
    assert any(x['attempt_id']==a['id'] for x in c.get(URL+'?status=completed&limit=100',headers=headers).json()['items'])
    update=c.put(endpoint,headers=headers,json={'points':0})
    assert update.status_code==200 and update.json()['items'][3]['manual_feedback'] is None
    assert c.get('/student/progress/me',headers=h).json()==progress
    assert c.get(f"/student/attempts/{a['id']}/review",headers=c.stranger_headers).status_code==404


def test_grading_authorization(setup,accounts):
    c,h,_,create=setup
    a=submitted(c,h,create())
    endpoints=[URL,f"{URL}/{a['id']}"]
    mutation=f"{URL}/{a['id']}/answers/{a['items'][3]['id']}"
    for headers in [h,c.stranger_headers]:
        for endpoint in endpoints: assert c.get(endpoint,headers=headers).status_code==403
        assert c.put(mutation,headers=headers,json={'points':0}).status_code==403
    with TestClient(app) as anon:
        for endpoint in endpoints: assert anon.get(endpoint).status_code==401
        assert anon.put(mutation,json={'points':0}).status_code==401
    _,inactive=accounts('LECTURER',active=False)
    assert c.put(mutation,headers=inactive,json={'points':0}).status_code==401
    _,staff=accounts('DEMONSTRATOR')
    assert c.put(mutation,headers={**staff,'X-CSRF-Token':''},json={'points':0}).status_code==403


@pytest.mark.parametrize('body',[{'points':-1},{'points':5},{'points':1.5},{'points':True},{'points':'1'},{},{'points':0,'unknown':1},{'points':0,'feedback':123},{'points':0,'feedback':'x'*20001}])
def test_grading_validation(setup,body):
    c,h,_,create=setup
    a=submitted(c,h,create())
    assert c.put(f"{URL}/{a['id']}/answers/{a['items'][3]['id']}",json=body).status_code==422


def test_grading_eligibility_and_blank(setup):
    c,h,_,create=setup
    quiz=create()
    a=start(c,h,quiz)
    endpoint=f"{URL}/{a['id']}/answers/{a['items'][3]['id']}"
    assert c.get(f"{URL}/{a['id']}").status_code==409
    assert c.put(endpoint,json={'points':0}).status_code==409
    assert not any(x['attempt_id']==a['id'] for x in c.get(URL+'?limit=100').json()['items'])
    assert c.post(f"/student/attempts/{a['id']}/submit",headers=h).status_code==200
    assert c.put(endpoint,json={'points':1}).status_code==422
    assert c.put(endpoint,json={'points':0,'feedback':'No response submitted'}).status_code==200
    assert c.put(f"{URL}/{a['id']}/answers/{a['items'][0]['id']}",json={'points':0}).status_code==422
    other=submitted(c,h,quiz)
    assert c.put(f"{URL}/{other['id']}/answers/{a['items'][3]['id']}",json={'points':0}).status_code==404
    assert c.get(f'{URL}/{uuid4()}').status_code==404
    assert c.get(URL+'?limit=0').status_code==422
    assert c.get(URL+'?status=unknown').status_code==422
    assert c.get(URL+'?limit=1').json()['limit']==1


def test_manual_database_constraint(setup):
    c,h,_,create=setup
    a=submitted(c,h,create())
    with Session(get_engine()) as s:
        item=s.get(AttemptAnswer,a['items'][0]['id'])
        item.manual_points=0
        with pytest.raises(IntegrityError): s.flush()
        s.rollback()


def test_0007_roundtrip_preserves_attempts():
    schema='dmi_manual_migration_'+uuid4().hex
    with get_engine().begin() as conn:
        conn.execute(CreateSchema(schema))
        try:
            conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
            config.attributes['connection']=conn
            command.upgrade(config,'0006')
            conn.execute(text("INSERT INTO users(id,email,role) VALUES (50,'migration-fixture@example.com','STUDENT')"))
            conn.execute(text("INSERT INTO quizzes(id,title,status) VALUES (50,'Historical','ACTIVE')"))
            aid=uuid4()
            conn.execute(text("INSERT INTO quiz_attempts(id,quiz_id,user_id,quiz_title,status,objective_total,objective_score,submitted_at) VALUES (:id,50,50,'Historical','SUBMITTED',0,0,now())"),{'id':aid})
            conn.execute(text("INSERT INTO attempt_answers(id,quiz_attempt_id,position,points,question_text,response_type,free_response) VALUES (50,:id,0,4,'Snapshot','FREE_RESPONSE','Proof')"),{'id':aid})
            before=dict(conn.execute(text('SELECT * FROM attempt_answers')).mappings().one())
            command.upgrade(config,'0007')
            after=dict(conn.execute(text('SELECT * FROM attempt_answers')).mappings().one())
            assert {k:after[k] for k in before}==before
            assert all(after[k] is None for k in ['manual_points','manual_feedback','graded_by_id','graded_at'])
            command.downgrade(config,'0006')
            assert dict(conn.execute(text('SELECT * FROM attempt_answers')).mappings().one())==before
            command.upgrade(config,'0007')
        finally:
            conn.execute(text('SET LOCAL search_path TO public'))
            conn.execute(DropSchema(schema,cascade=True))
