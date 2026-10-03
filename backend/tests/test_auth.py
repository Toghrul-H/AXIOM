"""Real PostgreSQL security tests; no authentication dependency overrides."""
import os
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete,select,text
from sqlalchemy.orm import Session
from app.main import app
from app.database import get_engine
from app.auth import COOKIE,digest,passwords,_failures
from app.auth_models import User,AuthSession
from app.auth_schemas import Credentials
from app.config import get_settings
from app.quiz_models import QuizAttempt
from app.scripts.create_admin import bootstrap_admin
from conftest import TEST_PASSWORD

pytestmark=[pytest.mark.integration,pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS')!='1',reason='Set RUN_POSTGRES_TESTS=1')]

@pytest.fixture
def client():
    _failures.clear()
    with TestClient(app) as client: yield client
    _failures.clear()

def test_registration_login_logout_and_normalization(client):
    email=f'auth-{uuid4().hex}@inf.elte.hu'
    payload={'email':'  '+email.upper()+'  ','password':TEST_PASSWORD}
    try:
        registered=client.post('/auth/register',json=payload)
        assert registered.status_code==201
        user=registered.json()
        assert user['role']=='STUDENT' and user['email']==email
        assert not {'password','password_hash','is_legacy'} & user.keys()
        assert client.post('/auth/register',json=payload).status_code==409
        with Session(get_engine()) as s:
            stored=s.get(User,user['id'])
            assert stored.password_hash.startswith('$argon2id$')
            assert stored.password_hash!=TEST_PASSWORD and passwords.verify(TEST_PASSWORD,stored.password_hash)
            # Verification lifecycle is exercised in test_email_verification.py.
            assert not stored.email_verified
            stored.email_verified=True
            s.commit()
        assert client.post('/auth/login',json={**payload,'password':'incorrect-password'}).status_code==401
        login=client.post('/auth/login',json=payload)
        assert login.status_code==200
        assert 'HttpOnly' in login.headers['set-cookie'] and 'SameSite=lax' in login.headers['set-cookie']
        token=client.cookies.get(COOKIE)
        with Session(get_engine()) as s:
            assert s.get(AuthSession,token) is None
            assert s.get(AuthSession,digest(token)).user_id==user['id']
        assert client.get('/auth/me').json()['user']==user
        csrf=login.json()['csrf_token']
        assert client.post('/auth/logout').status_code==403
        assert client.post('/auth/logout',headers={'X-CSRF-Token':csrf}).status_code==204
        assert client.get('/auth/me').status_code==401
        assert client.get('/auth/me',headers={'Cookie':f'{COOKIE}={token}'}).status_code==401
    finally:
        with Session(get_engine()) as s:
            s.execute(delete(User).where(User.email==email)); s.commit()

@pytest.mark.parametrize('role',['DEMONSTRATOR','LECTURER','ADMIN'])
def test_registration_rejects_privileged_fields(client,role):
    response=client.post('/auth/register',json={'email':'attack@example.com','password':TEST_PASSWORD,'role':role})
    assert response.status_code==422
    assert TEST_PASSWORD not in response.text
    assert client.post('/auth/register',json={'email':'attack@example.com','password':TEST_PASSWORD,'is_active':True}).status_code==422

def test_validation_does_not_echo_password(client):
    password='short-secret'
    response=client.post('/auth/register',json={'email':'invalid','password':password})
    assert response.status_code==422 and password not in response.text
    assert 'input' not in response.text

@pytest.mark.parametrize('path',['/auth/me','/questions','/question-metadata','/quizzes','/users','/student/quizzes','/student/attempts'])
def test_anonymous_protected_routes(client,path):
    assert client.get(path).status_code==401

@pytest.mark.parametrize('role',['STUDENT','DEMONSTRATOR','LECTURER','ADMIN'])
def test_role_matrix_and_manipulated_requests(client,accounts,role):
    user,h=accounts(role)
    client.headers.update(h)
    staff=role!='STUDENT'
    for path in ['/questions','/quizzes']:
        assert client.get(path).status_code==(200 if staff else 403)
    assert client.get('/users').status_code==(200 if role in {'LECTURER','ADMIN'} else 403)
    # Authentication/authorization runs before invalid IDs or invalid payloads.
    for method,path,body in [('post','/questions',{}),('patch','/questions/99999999',{}),('delete','/questions/99999999',None),('post','/questions/99999999/check',{}),('post','/quizzes',{}),('put','/quizzes/99999999',{})]:
        response=client.request(method,path,json=body)
        assert response.status_code in ({404,422} if staff else {403})
    for elevated in ['DEMONSTRATOR','LECTURER','ADMIN']:
        assert client.post(f"/users/{user['id']}/role",json={'role':elevated}).status_code in {403,422}
    assert client.get('/student/attempts').status_code==(200 if role=='STUDENT' else 403)

def test_hierarchy_and_immediate_session_revocation(client,accounts):
    admin,ah=accounts('ADMIN'); lecturer,lh=accounts('LECTURER'); student,sh=accounts()
    base=f"/users/{student['id']}"
    assert client.post(base+'/role',headers=lh,json={'role':'LECTURER'}).status_code==403
    assert client.post(base+'/status',headers=lh,json={'is_active':False}).status_code==403
    assert client.post(base+'/role',headers=lh,json={'role':'DEMONSTRATOR'}).json()['role']=='DEMONSTRATOR'
    assert client.get('/auth/me',headers=sh).status_code==401
    login=client.post('/auth/login',json={'email':student['email'],'password':TEST_PASSWORD})
    assert login.status_code==200
    dh={'Cookie':f'{COOKIE}={client.cookies.get(COOKIE)}','X-CSRF-Token':login.json()['csrf_token']}
    assert client.get('/questions',headers=dh).status_code==200
    assert client.post(f"/users/{lecturer['id']}/role",headers=dh,json={'role':'DEMONSTRATOR'}).status_code==403
    assert client.post(base+'/status',headers=lh,json={'is_active':False}).status_code==200
    assert client.get('/questions',headers=dh).status_code==401
    assert client.post('/auth/login',json={'email':student['email'],'password':TEST_PASSWORD}).status_code==401
    assert client.post(base+'/status',headers=lh,json={'is_active':True}).status_code==200
    assert client.get('/questions',headers=dh).status_code==401 # old sessions stay revoked
    assert client.post('/auth/login',json={'email':student['email'],'password':TEST_PASSWORD}).status_code==200
    assert client.post(base+'/role',headers=ah,json={'role':'LECTURER'}).status_code==200
    assert client.post(base+'/status',headers=lh,json={'is_active':False}).status_code==403
    assert client.post(base+'/role',headers=lh,json={'role':'DEMONSTRATOR'}).status_code==403
    assert client.post(base+'/status',headers=ah,json={'is_active':False}).status_code==200
    assert client.post(base+'/status',headers=ah,json={'is_active':True}).status_code==200
    assert client.post(base+'/role',headers=ah,json={'role':'STUDENT'}).status_code==200
    for h in [ah,lh]:
        assert client.post(f"/users/{admin['id']}/status",headers=h,json={'is_active':False}).status_code==403
        assert client.post(base+'/role',headers=h,json={'role':'ADMIN'}).status_code==422
        assert client.post(base+'/role',headers=h,json={'role':'DEMONSTRATOR','is_active':True}).status_code==422
        assert client.post(base+'/status',headers=h,json={'is_active':'false'}).status_code==422

def test_inactive_and_expired_sessions(client,accounts):
    user,h=accounts(active=False)
    assert client.get('/auth/me',headers=h).status_code==401
    assert client.post('/auth/login',json={'email':user['email'],'password':TEST_PASSWORD}).status_code==401
    active,h=accounts()
    with Session(get_engine()) as s:
        auth=s.scalar(select(AuthSession).where(AuthSession.user_id==active['id']))
        auth.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1); s.commit()
    assert client.get('/auth/me',headers=h).status_code==401

def test_csrf_and_origin_security(client,accounts):
    user,h=accounts('LECTURER')
    assert client.post('/quizzes',headers={'Cookie':h['Cookie']},json={}).status_code==403
    assert client.post('/quizzes',headers={**h,'X-CSRF-Token':'forged'},json={}).status_code==403
    for path in ['/auth/login','/auth/register']:
        assert client.post(path,headers={'Origin':'https://attacker.example'},json={'email':user['email'],'password':TEST_PASSWORD}).status_code==403
        assert client.post(path,data={'email':user['email'],'password':TEST_PASSWORD}).status_code==415
    assert client.post('/quizzes',headers={**h,'Sec-Fetch-Site':'cross-site'},json={}).status_code==403
    # Non-ASCII hostile header bytes must be rejected, not cause a server error.
    assert client.post('/quizzes',headers={b'Cookie':h['Cookie'].encode(),b'X-CSRF-Token':b'\xff'},json={}).status_code==403


def test_https_cookie_configuration(client,accounts,monkeypatch):
    user,_=accounts()
    monkeypatch.setattr(get_settings(),'auth_cookie_secure',True)
    response=client.post('/auth/login',json={'email':user['email'],'password':TEST_PASSWORD})
    assert response.status_code==200
    assert 'Secure' in response.headers['set-cookie']
    assert 'HttpOnly' in response.headers['set-cookie']

def test_rate_limit(client,monkeypatch):
    monkeypatch.setattr(get_settings(),'auth_requests_per_minute',2)
    for _ in range(2):
        assert client.post('/auth/login',json={'email':'unknown@example.com','password':TEST_PASSWORD}).status_code==401
    assert client.post('/auth/login',json={'email':'unknown@example.com','password':TEST_PASSWORD}).status_code==429

def test_bootstrap_refuses_second_admin(accounts):
    accounts('ADMIN')
    with Session(get_engine()) as s, pytest.raises(ValueError,match='already exists'):
        bootstrap_admin(s,Credentials(email='bootstrap@example.com',password=TEST_PASSWORD))

def test_legacy_history_is_not_inherited(client,accounts):
    _,h=accounts()
    with Session(get_engine()) as s:
        legacy=s.scalar(select(User).where(User.is_legacy.is_(True)))
        assert legacy and not legacy.is_active and legacy.password_hash is None
        attempts=list(s.scalars(select(QuizAttempt).where(QuizAttempt.user_id==legacy.id)))
        for attempt in attempts:
            assert client.get(f'/student/attempts/{attempt.id}',headers={**h,'X-Development-Session':str(attempt.development_session_id)}).status_code==404
    assert client.get('/student/attempts',headers=h).json()==[]


@pytest.mark.parametrize('role',['DEMONSTRATOR','LECTURER','ADMIN'])
def test_authorized_question_crud(client,accounts,role):
    from app.models import Question
    _,h=accounts(role)
    client.headers.update(h)
    topic=client.get('/question-metadata').json()['topics'][0]['id']
    response=client.post('/questions',json={'topic_id':topic,'difficulty':'easy','response_type':'TRUE_FALSE','skill_type':'DEFINITION','question_text':'Temporary RBAC question','correct_boolean':False})
    assert response.status_code==201
    question_id=response.json()['id']
    try:
        assert client.get(f'/questions/{question_id}').status_code==200
        assert client.patch(f'/questions/{question_id}',json={'question_text':'Updated RBAC question'}).status_code==200
        assert client.post(f'/questions/{question_id}/check',json={'boolean_answer':False}).status_code==200
        assert client.delete(f'/questions/{question_id}').status_code==204
        assert client.get(f'/questions/{question_id}').status_code==404
    finally:
        with Session(get_engine()) as s:
            s.execute(delete(Question).where(Question.id==question_id)); s.commit()
