import os
from pathlib import Path
from uuid import uuid4
import pytest
from sqlalchemy import text
from sqlalchemy.schema import CreateSchema, DropSchema
from alembic import command
from alembic.config import Config
from app.database import get_engine
from test_assessments import setup, BASE

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS') != '1', reason='Requires local PostgreSQL')]

@pytest.mark.parametrize('role', ['LECTURER','ADMIN'])
def test_shared_policy_rules_and_total_roundtrip(setup, role):
    client,h,cid,_,_ = setup(role)
    path=f'{BASE}/{cid}'
    assert client.get(path+'/rules',headers=h).json()['maximum_total_score'] is None
    for code,maximum,passing in [('MIDTERM',40,16),('ENDTERM',35,14),('COURSEWORK',20,8),('SHORT_QUIZZES',20,8)]:
        response=client.put(path+'/policies/'+code,headers=h,json={'maximum_score':maximum,'passing_score':passing,'topics':'A & B','duration_minutes':75,'assessment_count':10 if code=='SHORT_QUIZZES' else 1,'conduct_instructions':'Bring ID','retake_rules':'Professor configured'})
        assert response.status_code==200,response.text
        assert response.json()['topics']=='A & B'
    boundaries=[{'grade':i+1,'minimum_score':v} for i,v in enumerate([0,48,66,84,102])]
    result=client.put(path+'/rules',headers=h,json={'plus_points_maximum':'10.5','plus_points_rules':'0.5 for partial homework; not for topping up failures','total_score_rules':'All components must pass first','grade_boundaries':boundaries})
    assert result.status_code==200,result.text
    assert result.json()['maximum_total_score']=='125.50'
    assert len(client.get(path,headers=h).json()['policies'])==4
    assert len(result.json()['grade_boundaries'])==5
    assert client.put(path+'/policies/MIDTERM',headers=h,json={'maximum_score':0,'passing_score':0}).status_code==422
    assert client.get(path+'/rules',headers=h).json()['maximum_total_score']=='125.50'
    invalid=[{**row,'minimum_score':999 if row['grade']==5 else row['minimum_score']} for row in boundaries]
    assert client.put(path+'/rules',headers=h,json={'plus_points_maximum':'10.5','grade_boundaries':invalid}).status_code==422
    assert client.get(path+'/rules',headers=h).json()['grade_boundaries'][-1]['minimum_score']=='102.00'
    assert client.put(path+'/rules',headers=h,json={'plus_points_maximum':0}).json()['grade_boundaries']==[]
    assert client.put(path+'/policies/ENDTERM',headers=h,json={}).json()['maximum_score'] is None
    assert client.get(path+'/rules',headers=h).json()['maximum_total_score'] is None

@pytest.mark.parametrize('data', [ {'maximum_score':10,'passing_score':11}, {'maximum_score':-1}, {'passing_score':'NaN'}, {'maximum_score':'1.234'}, {'duration_minutes':0}, {'duration_minutes':1.5}, {'assessment_count':True}, {'topics':' '}, {'assessment_mode':'x'*20001} ])
def test_policy_validation(setup,data):
    client,h,cid,_,_=setup()
    assert client.put(f'{BASE}/{cid}/policies/ENDTERM',headers=h,json=data).status_code==422

def test_rule_validation_and_permissions(setup,accounts):
    client,h,cid,_,_=setup()
    path=f'{BASE}/{cid}'
    for data in [{'plus_points_maximum':-1}, {'grade_boundaries':[{'grade':2,'minimum_score':0}]}, {'grade_boundaries':[{'grade':i,'minimum_score':0} for i in range(1,6)]}]:
        assert client.put(path+'/rules',headers=h,json=data).status_code==422
    for role in ('STUDENT','DEMONSTRATOR'):
        _,denied=accounts(role)
        for method,url in [('PUT',path+'/policies/ENDTERM'),('GET',path+'/rules'),('PUT',path+'/rules')]:
            assert client.request(method,url,headers=denied,json={}).status_code==403
            assert client.request(method,url,json={}).status_code==401
    cookie_only={'Cookie':h['Cookie']}
    assert client.put(path+'/policies/ENDTERM',headers=cookie_only,json={}).status_code==403
    assert client.put(path+'/rules',headers=cookie_only,json={}).status_code==403
    assert client.put(path+'/policies/UNKNOWN',headers=h,json={}).status_code==422

def test_submission_groups_persistence_validation_and_legacy_clients(setup):
    client,h,cid,_,_=setup()
    path=f'{BASE}/{cid}/events'
    data={'event_type':'COURSEWORK_HAND_IN','submission_deadline_date':'2027-05-01','submission_deadline_time':'10:00','submission_venue':'Main room','submission_instructions':'Handwritten',
        'group_deadlines':[{'group_identifier':' G1 ','deadline_date':'2027-05-02','venue':'R1'},{'group_identifier':'G2','deadline_time':'11:00'}]}
    result=client.post(path,headers=h,json=data)
    assert result.status_code==201,result.text
    ep=path+'/'+str(result.json()['id'])
    assert result.json()['group_deadlines'][0]['group_identifier']=='G1'
    legacy=client.put(ep,headers=h,json={'event_type':'COURSEWORK_HAND_IN','notes':'Legacy client'})
    assert legacy.status_code==200 and len(legacy.json()['group_deadlines'])==2
    assert legacy.json()['submission_venue']=='Main room'
    assert client.put(ep,headers=h,json={'event_type':'ENDTERM'}).status_code==409
    for changes in [{'group_deadlines':[{'group_identifier':'G1'},{'group_identifier':' G1 '}]}, {'submission_deadline_time':'10:00Z'}, {'group_deadlines':[{'group_identifier':'G1','deadline_time':'10:00Z'}]}, {'group_deadlines':[{'group_identifier':' '}]}, {'event_type':'ENDTERM'}]:
        assert client.put(ep,headers=h,json={**data,**changes}).status_code==422
    cleared=client.put(ep,headers=h,json={'event_type':'COURSEWORK_HAND_IN','group_deadlines':[], 'submission_deadline_date':None,'submission_deadline_time':None,'submission_venue':None,'submission_instructions':None})
    assert cleared.status_code==200 and cleared.json()['group_deadlines']==[]
    assert client.put(ep,headers=h,json={'event_type':'ENDTERM','seating_plan':'Rows assigned at arrival'}).status_code==200
    assert client.delete(ep,headers=h).status_code==204

def test_0012_preserves_existing_events_and_nullable_data():
    schema='dmi_policy_'+uuid4().hex
    with get_engine().begin() as conn:
        conn.execute(CreateSchema(schema))
        try:
            conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
            config.attributes['connection']=conn
            command.upgrade(config,'0011')
            cid=conn.scalar(text("INSERT INTO assessment_configurations(academic_year_start,term,display_label) VALUES (2026,'FALL','Preserved') RETURNING id"))
            conn.execute(text("INSERT INTO assessment_events(configuration_id,event_type,start_time,end_time,writing_start_time,writing_end_time,latest_arrival_time) VALUES (:cid,'ENDTERM','10:00','12:00','10:15','11:45','10:05')"),{'cid':cid})
            before=dict(conn.execute(text('SELECT * FROM assessment_events')).mappings().one())
            command.upgrade(config,'0012')
            after=dict(conn.execute(text('SELECT * FROM assessment_events')).mappings().one())
            for name in ('seating_plan','submission_deadline_date','submission_deadline_time','submission_venue','submission_instructions'):
                assert after.pop(name) is None
            assert after==before
            assert conn.scalar(text('SELECT count(*) FROM assessment_policies'))==0
            conn.execute(text("INSERT INTO assessment_policies(configuration_id,code,maximum_score) VALUES (:cid,'ENDTERM',40)"),{'cid':cid})
            conn.execute(text('DELETE FROM assessment_configurations WHERE id=:cid'),{'cid':cid})
            assert conn.scalar(text('SELECT count(*) FROM assessment_policies'))==0
            command.downgrade(config,'0011')
            command.upgrade(config,'0012')
        finally:
            conn.execute(text('SET LOCAL search_path TO public'))
            conn.execute(DropSchema(schema,cascade=True))
