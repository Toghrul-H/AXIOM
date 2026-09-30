import os
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from app.main import app
from app.database import get_engine
from app.models import Question
from app.quiz_models import Quiz, QuizAttempt, AttemptAnswer

pytestmark = [pytest.mark.integration,pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS') != '1',reason='Set RUN_POSTGRES_TESTS=1')]

@pytest.fixture
def setup(accounts):
    client = TestClient(app)
    _, staff = accounts('LECTURER')
    _, headers = accounts()
    _, client.stranger_headers = accounts()
    client.headers.update(staff)
    questions, quizzes = [], []
    topic = client.get('/question-metadata').json()['topics'][0]['id']
    for kind in ['SINGLE_CHOICE','MULTIPLE_SELECT','TRUE_FALSE','FREE_RESPONSE','TRUE_FALSE']:
        payload = dict(topic_id=topic,difficulty='easy',response_type=kind,skill_type='DEFINITION',question_text=f'Test {kind} {uuid4()}',explanation=f'Solution for {kind}')
        if kind.endswith('CHOICE') or kind == 'MULTIPLE_SELECT':
            payload['options'] = [{'text':'A','is_correct':True},{'text':'B','is_correct':kind=='MULTIPLE_SELECT'},{'text':'C','is_correct':False}]
        elif kind == 'TRUE_FALSE': payload['correct_boolean'] = False
        else: payload['expected_answer'] = 'Reference proof'
        r = client.post('/questions',json=payload)
        assert r.status_code == 201, r.text
        questions.append(r.json())
    def create(status='ACTIVE',order=None):
        entries = order or questions
        r = client.post('/quizzes',json=dict(title='Temporary quiz',status=status,questions=[{'question_id':q['id'],'points':i+1} for i,q in enumerate(entries)]))
        assert r.status_code == 201,r.text
        quizzes.append(r.json()['id'])
        return r.json()
    yield client,headers,questions,create
    with Session(get_engine()) as s:
        s.execute(delete(QuizAttempt).where(QuizAttempt.quiz_id.in_(quizzes)))
        s.execute(delete(Quiz).where(Quiz.id.in_(quizzes)))
        s.execute(delete(Question).where(Question.id.in_([q['id'] for q in questions])))
        s.commit()
    client.close()


def start(c,h,q):
    r = c.post(f"/student/quizzes/{q['id']}/attempts",headers=h)
    assert r.status_code == 201,r.text
    return r.json()


def assert_hidden(value):
    if isinstance(value,dict):
        assert not {'expected_answer','correct_boolean','explanation','is_correct','correct_option_ids','points_awarded'} & value.keys()
        for v in value.values(): assert_hidden(v)
    elif isinstance(value,list):
        for v in value: assert_hidden(v)


def test_complete_workflow_and_snapshots(setup):
    c,h,questions,create = setup
    quiz = create()
    assert [q['question_id'] for q in quiz['questions']] == [q['id'] for q in questions]
    assert [q['position'] for q in quiz['questions']] == list(range(5))
    a = start(c,h,quiz)
    base = f"/student/attempts/{a['id']}"
    assert_hidden(a)
    assert c.get(base+'/review',headers=h).status_code == 409
    items = a['items']
    def save(index,body):
        r = c.put(base+f"/answers/{items[index]['id']}",headers=h,json=body)
        assert r.status_code == 200,r.text
        assert_hidden(r.json())
    save(0,{'selected_option_ids':[items[0]['options'][2]['id']]})
    save(0,{'selected_option_ids':[items[0]['options'][0]['id']]})
    save(1,{'selected_option_ids':[items[1]['options'][0]['id']]}) # partial is wrong
    save(2,{'boolean_answer':False})
    save(3,{'free_response':'My written proof'})
    # Fifth question intentionally unanswered.
    with Session(get_engine()) as s:
        persisted = s.get(QuizAttempt,a['id'])
        assert persisted.status == 'IN_PROGRESS'
        assert persisted.items[3].free_response == 'My written proof'
        assert all(i.is_correct is None for i in persisted.items)
    reloaded = c.get(base,headers=h).json()
    assert reloaded['items'][2]['boolean_answer'] is False
    assert_hidden(reloaded)
    # Bank edits during an attempt cannot alter the question it started with.
    assert c.patch(f"/questions/{questions[2]['id']}",json={'correct_boolean':True,'question_text':'Changed later','explanation':'Changed solution'}).status_code==200
    r = c.post(base+'/submit',headers=h)
    assert r.status_code == 200,r.text
    review = r.json()
    assert review['objective_score']==4 and review['objective_total']==11
    assert (review['correct_count'],review['incorrect_count'],review['ungraded_count'],review['unanswered_objective_count'])==(2,2,1,1)
    assert review['items'][3]['is_correct'] is None and review['items'][3]['points_awarded'] is None
    assert review['items'][3]['free_response']=='My written proof'
    assert review['items'][3]['expected_answer']=='Reference proof'
    for i in review['items']: assert i['explanation'].startswith('Solution for')
    assert review['items'][4]['answered'] is False and review['items'][4]['correct_boolean'] is False
    assert review['items'][2]['correct_boolean'] is False
    assert c.put(base+f"/answers/{items[0]['id']}",headers=h,json={}).status_code==409
    assert c.post(base+'/submit',headers=h).json()==review
    # Editing options/reference and deleting the source must preserve history.
    assert c.patch(f"/questions/{questions[0]['id']}",json={'options':[{'text':'NEW','is_correct':True},{'text':'OTHER','is_correct':False}]}).status_code==200
    assert c.patch(f"/questions/{questions[3]['id']}",json={'expected_answer':'New reference','explanation':'New explanation'}).status_code==200
    assert c.delete(f"/questions/{questions[0]['id']}").status_code==204
    assert c.get(base+'/review',headers=h).json()==review
    assert c.get('/student/attempts',headers=h).json()[0]['id']==a['id']
    with Session(get_engine()) as s:
        assert s.get(QuizAttempt,a['id']).objective_score==4


def test_invalid_ids_answer_shapes_and_identity(setup):
    c,h,qs,create = setup
    a = start(c,h,create())
    base=f"/student/attempts/{a['id']}"
    choice=a['items'][0]; multiple=a['items'][1]
    for payload in [{'selected_option_ids':[multiple['options'][0]['id']]},{'selected_option_ids':[choice['options'][0]['id']]*2},{'boolean_answer':True},{'selected_option_ids':[o['id'] for o in choice['options'][:2]]}]:
        assert c.put(base+f"/answers/{choice['id']}",headers=h,json=payload).status_code==422
    assert c.put(base+f"/answers/{a['items'][2]['id']}",headers=h,json={'boolean_answer':'false'}).status_code==422
    assert c.put(base+'/answers/99999999',headers=h,json={}).status_code==404
    assert c.get(base,headers=c.stranger_headers).status_code==404
    assert c.get(base).status_code==403
    assert c.get(f'/student/attempts/{uuid4()}',headers=h).status_code==404
    assert c.get('/quizzes/99999999').status_code==404
    assert c.put('/quizzes/99999999',json={'title':'Missing'}).status_code==404
    assert c.post('/student/quizzes/99999999/attempts',headers=h).status_code==404
    assert c.post('/quizzes',json={'title':'Invalid','status':'ACTIVE','questions':[]}).status_code==422
    assert c.post('/quizzes',json={'title':'Invalid','questions':[{'question_id':99999999}]}).status_code==422
    assert c.post('/quizzes',json={'title':'Invalid','questions':[{'question_id':qs[0]['id']}]*2}).status_code==422
    assert c.post('/quizzes',json={'title':'Invalid','questions':[{'question_id':qs[0]['id'],'points':0}]}).status_code==422


def test_composition_status_and_full_multiple_select(setup):
    c,h,qs,create=setup
    quiz=create('DRAFT')
    assert c.post(f"/student/quizzes/{quiz['id']}/attempts",headers=h).status_code==409
    r=c.put(f"/quizzes/{quiz['id']}",json={'title':'Reordered','status':'ACTIVE','questions':[{'question_id':q['id'],'points':2} for q in reversed(qs)]})
    assert r.status_code==200,r.text
    assert [e['question_id'] for e in r.json()['questions']]==[q['id'] for q in reversed(qs)]
    a=start(c,h,quiz); base=f"/student/attempts/{a['id']}"
    item=next(i for i in a['items'] if i['response_type']=='MULTIPLE_SELECT')
    assert c.put(base+f"/answers/{item['id']}",headers=h,json={'selected_option_ids':[o['id'] for o in item['options'][:2]]}).status_code==200
    result=c.post(base+'/submit',headers=h).json()
    assert result['objective_score']==2 and result['objective_total']==8
    assert result['correct_count']==1 and result['incorrect_count']==3
    assert c.patch(f"/questions/{qs[0]['id']}",json={'is_active':False}).status_code==200
    assert c.post(f"/student/quizzes/{quiz['id']}/attempts",headers=h).status_code==409
    assert quiz['id'] not in [x['id'] for x in c.get('/student/quizzes',headers=h).json()]


def test_free_response_only_and_clearing_answers(setup):
    c,h,qs,create=setup
    a=start(c,h,create(order=[qs[3]])); base=f"/student/attempts/{a['id']}"
    item=a['items'][0]
    assert c.put(base+f"/answers/{item['id']}",headers=h,json={'free_response':'Some text'}).status_code==200
    assert c.put(base+f"/answers/{item['id']}",headers=h,json={}).json()['items'][0]['free_response'] is None
    review=c.post(base+'/submit',headers=h).json()
    assert review['objective_total']==0 and review['ungraded_count']==1
    assert review['items'][0]['is_correct'] is None


def test_concurrent_submission_is_idempotent(setup):
    from concurrent.futures import ThreadPoolExecutor
    c,h,qs,create=setup
    a=start(c,h,create(order=[qs[2]]))
    base=f"/student/attempts/{a['id']}"
    item=a['items'][0]
    assert c.put(base+f"/answers/{item['id']}",headers=h,json={'boolean_answer':False}).status_code==200
    def submit():
        with TestClient(app) as other:
            response=other.post(base+'/submit',headers=h)
            assert response.status_code==200
            return response.json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        first,second=list(pool.map(lambda _:submit(),range(2)))
    assert first==second
    assert first['objective_score']==1
    response=c.get(base,headers=h)
    assert response.headers['Cache-Control']=='no-store'
    assert_hidden(response.json())
    stranger=c.stranger_headers
    assert c.get(base+'/review',headers=stranger).status_code==404
    assert c.post(base+'/submit',headers=stranger).status_code==404
    assert c.put(base+f"/answers/{item['id']}",headers=stranger,json={}).status_code==404


def test_topic_snapshot_and_unicode_answer(setup):
    c,h,qs,create=setup
    a=start(c,h,create(order=[qs[3]]))
    item=a['items'][0]
    assert item['topic_slug'] == qs[3]['topic']['slug']
    base=f"/student/attempts/{a['id']}"
    answer='A ∩ B = {2, 4}\nR⁻¹ = {(2,1), (3,2)}\n∀x ∈ A, f(x) ∈ B'
    assert c.put(base+f"/answers/{item['id']}",headers=h,json={'free_response':answer}).status_code==200
    other_topic=next(t for t in c.get('/question-metadata').json()['topics'] if t['slug']!=item['topic_slug'])
    assert c.patch(f"/questions/{qs[3]['id']}",json={'topic_id':other_topic['id']}).status_code==200
    resumed=c.get(base,headers=h).json()['items'][0]
    assert resumed['topic_slug']==item['topic_slug']
    assert resumed['free_response']==answer
    result=c.post(base+'/submit',headers=h).json()['items'][0]
    assert result['free_response']==answer and result['is_correct'] is None
    assert c.get(base+'/review',headers=h).json()['items'][0]['free_response']==answer
    # Pre-4.1 snapshots can still load and review with unknown topic context.
    with Session(get_engine()) as s:
        s.get(AttemptAnswer,item['id']).topic_slug=None
        s.commit()
    assert c.get(base+'/review',headers=h).json()['items'][0]['topic_slug'] is None


def test_cross_student_active_attempt_isolation(setup):
    c,h,qs,create=setup
    a=start(c,h,create())
    base=f"/student/attempts/{a['id']}"
    other=c.stranger_headers
    assert c.get(base,headers=other).status_code==404
    assert c.put(base+f"/answers/{a['items'][0]['id']}",headers=other,json={}).status_code==404
    assert c.post(base+'/submit',headers=other).status_code==404
    assert c.get(base+'/review',headers=other).status_code==404
    assert a['id'] not in [x['id'] for x in c.get('/student/attempts',headers=other).json()]
    assert c.get(base,headers=h).json()['status']=='IN_PROGRESS'
    assert c.post(base+'/submit',headers=h).status_code==200
    assert c.get(base+'/review',headers=h).status_code==200
