import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.main import app
from app.database import get_engine
from app.quiz_models import AttemptAnswer
from test_quizzes import setup, start

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS') != '1', reason='Set RUN_POSTGRES_TESTS=1')]
URL = '/student/progress/me'


def test_progress_anonymous():
    with TestClient(app) as c:
        assert c.get(URL).status_code == 401


@pytest.mark.parametrize('role', ['LECTURER', 'DEMONSTRATOR', 'ADMIN'])
def test_progress_staff_denied(accounts, role):
    _, headers = accounts(role)
    with TestClient(app) as c:
        assert c.get(URL, headers=headers).status_code == 403


def test_progress_inactive(accounts):
    _, headers = accounts(active=False)
    with TestClient(app) as c:
        assert c.get(URL, headers=headers).status_code == 401


def test_progress_empty(accounts):
    _, headers = accounts()
    with TestClient(app) as c:
        r = c.get(URL, headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data['overview'] == dict(completed_quizzes=0, completed_attempts=0, questions_answered=0, auto_graded_questions=0, auto_graded_correct=0, auto_graded_accuracy=None)
        assert len(data['topics']) == 7 and len(data['skills']) == 8
        assert all(x['accuracy_percent'] is None and x['answered_count'] == 0 for x in data['topics'] + data['skills'])
        assert data['recent_attempts'] == []


def test_progress_history_ownership_and_snapshots(setup):
    c, h, questions, create = setup
    metadata = c.get('/question-metadata').json()
    logic = next(t['id'] for t in metadata['topics'] if t['slug'] == 'logic')
    sets = next(t['id'] for t in metadata['topics'] if t['slug'] == 'sets')
    for q in questions:
        assert c.patch(f"/questions/{q['id']}", json={'topic_id': logic, 'skill_type': 'PROOF' if q['response_type'] == 'FREE_RESPONSE' else 'DEFINITION'}).status_code == 200
    quiz = create()
    ids = []
    for _ in range(2):
        a = start(c, h, quiz)
        ids.append(a['id'])
        base = f"/student/attempts/{a['id']}"
        answers = [dict(selected_option_ids=[a['items'][0]['options'][0]['id']]), dict(selected_option_ids=[a['items'][1]['options'][0]['id']]), dict(boolean_answer=False), dict(free_response='A proof')]
        for item, answer in zip(a['items'], answers):
            assert c.put(base + f"/answers/{item['id']}", headers=h, json=answer).status_code == 200
        assert c.post(base+'/submit', headers=h).status_code == 200
    start(c, h, quiz)  # unfinished attempt is excluded
    foreign = start(c, c.stranger_headers, quiz)
    c.post(f"/student/attempts/{foreign['id']}/submit", headers=c.stranger_headers)
    r = c.get(URL, headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data['overview'] == dict(completed_quizzes=1, completed_attempts=2, questions_answered=8, auto_graded_questions=6, auto_graded_correct=4, auto_graded_accuracy=66.67)
    topic = next(t for t in data['topics'] if t['slug'] == 'logic')
    assert (topic['answered_count'], topic['auto_graded_count'], topic['correct_count']) == (8,6,4)
    proof = next(s for s in data['skills'] if s['code'] == 'PROOF')
    assert (proof['answered_count'], proof['auto_graded_count'], proof['accuracy_percent']) == (2,0,None)
    definition = next(s for s in data['skills'] if s['code'] == 'DEFINITION')
    assert definition['accuracy_percent'] == 66.67
    assert {a['id'] for a in data['recent_attempts']} == set(ids)
    assert all(a['total_question_count'] == 5 and a['objective_score'] == 4 and a['objective_total'] == 11 for a in data['recent_attempts'])
    assert c.get(URL+'?user_id=999999', headers=h).json() == data
    other = c.get(URL, headers=c.stranger_headers).json()
    assert other['overview']['completed_attempts'] == 1
    assert other['overview']['questions_answered'] == 0
    assert other['overview']['auto_graded_accuracy'] is None
    for q in questions:
        assert c.patch(f"/questions/{q['id']}", json={'topic_id':sets, 'skill_type':'APPLICATION', 'question_text':'Edited later'}).status_code == 200
    assert c.get(URL, headers=h).json() == data
    assert c.delete(f"/questions/{questions[0]['id']}").status_code == 204
    assert c.get(URL, headers=h).json() == data


def test_progress_legacy_metadata_and_blank_written(setup):
    c,h,questions,create = setup
    a = start(c,h,create())
    base = f"/student/attempts/{a['id']}"
    assert c.put(base+f"/answers/{a['items'][3]['id']}", headers=h, json={'free_response':'   '}).status_code == 422
    assert c.put(base+f"/answers/{a['items'][2]['id']}", headers=h, json={'boolean_answer':False}).status_code == 200
    assert c.post(base+'/submit',headers=h).status_code == 200
    with Session(get_engine()) as s:
        item=s.get(AttemptAnswer,a['items'][2]['id'])
        item.topic_slug=None
        item.skill_code=None
        s.commit()
    data=c.get(URL,headers=h).json()
    assert data['overview']['questions_answered']==1
    assert data['overview']['auto_graded_accuracy']==100
    assert data['unattributed_skill']['correct_count']==1
    assert data['unattributed_topic']['correct_count']==1
    assert all(x['auto_graded_count']==0 for x in data['topics']+data['skills'])


def test_progress_recent_limit_and_full_aggregate(setup):
    c,h,_,create=setup
    quiz=create()
    ids=[]
    for _ in range(11):
        a=start(c,h,quiz)
        ids.append(a['id'])
        assert c.post(f"/student/attempts/{a['id']}/submit",headers=h).status_code==200
    data=c.get(URL,headers=h).json()
    assert data['overview']['completed_attempts']==11
    assert data['overview']['completed_quizzes']==1
    assert [a['id'] for a in data['recent_attempts']]==list(reversed(ids[1:]))
