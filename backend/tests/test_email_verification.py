import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.main import app
from app.database import get_engine
from app.auth import _failures, digest
from app.auth_models import User, EmailVerification
from app.services.email_verification import get_verification_delivery
from conftest import TEST_PASSWORD

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS') != '1', reason='Requires local PostgreSQL')]

@pytest.fixture
def flow():
    sent = []
    email = f'verify-{uuid4().hex}@inf.elte.hu'
    app.dependency_overrides[get_verification_delivery] = lambda: lambda email, token: sent.append((email, token))
    _failures.clear()
    try:
        with TestClient(app) as client:
            yield client, email, sent
    finally:
        app.dependency_overrides.pop(get_verification_delivery, None)
        with Session(get_engine()) as session:
            session.execute(delete(User).where(User.email == email))
            session.commit()
        _failures.clear()

def register(client, email):
    return client.post('/auth/register', json={'email': email, 'password': TEST_PASSWORD})

def test_registration_verification_login_and_single_use(flow):
    client, email, sent = flow
    response = register(client, '  ' + email.upper() + '  ')
    assert response.status_code == 201
    assert response.json()['role'] == 'STUDENT'
    assert sent[0][0] == email
    token = sent[0][1]
    assert token not in response.text and 'set-cookie' not in response.headers
    with Session(get_engine()) as session:
        user = session.get(User, response.json()['id'])
        assert not user.email_verified
        record = session.get(EmailVerification, user.id)
        assert record.token_hash == digest(token) and record.token_hash != token
    credentials = {'email': email, 'password': TEST_PASSWORD}
    assert client.post('/auth/login', json=credentials).status_code == 403
    assert client.get('/student/progress/me').status_code == 401
    assert client.post('/auth/verify-email', json={'token': token}).status_code == 204
    assert client.post('/auth/verify-email', json={'token': token}).status_code == 400
    assert client.post('/auth/login', json=credentials).status_code == 200
    assert client.get('/questions').status_code == 403
    assert client.post('/auth/resend-verification', json={'email': email}).status_code == 202
    assert len(sent) == 1

@pytest.mark.parametrize('email', ['user@gmail.com', 'user@elte.hu', 'user@student.elte.hu', 'user@inf.elte.hu.example.com', 'user@example.com?x=@inf.elte.hu'])
def test_invalid_domains(flow, email):
    client, _, sent = flow
    response = register(client, email)
    assert response.status_code == 422
    if '?' not in email:
        assert 'Please register using your ELTE Faculty of Informatics email address (@inf.elte.hu).' in response.text
    assert not sent

@pytest.mark.parametrize('extra', [{'role': 'ADMIN'}, {'email_verified': True}])
def test_public_cannot_select_role_or_verification(flow, extra):
    client, email, sent = flow
    assert client.post('/auth/register', json={'email': email, 'password': TEST_PASSWORD, **extra}).status_code == 422
    assert not sent

def test_expiration_resend_supersession_and_cooldown(flow):
    client, email, sent = flow
    user_id = register(client, email).json()['id']
    old = sent[0][1]
    client.post('/auth/resend-verification', json={'email': email})
    assert len(sent) == 1
    with Session(get_engine()) as session:
        record = session.get(EmailVerification, user_id)
        record.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
        record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.commit()
    assert client.post('/auth/verify-email', json={'token': old}).status_code == 400
    response = client.post('/auth/resend-verification', json={'email': email})
    assert response.status_code == 202 and len(sent) == 2
    assert sent[1][1] != old and sent[1][1] not in response.text
    assert client.post('/auth/verify-email', json={'token': old}).status_code == 400
    assert client.post('/auth/verify-email', json={'token': sent[1][1]}).status_code == 204
    unknown = client.post('/auth/resend-verification', json={'email': 'unknown@inf.elte.hu'})
    assert unknown.json() == response.json()

@pytest.mark.parametrize('token', ['invalid-token-fixture', '!' * 43, 'a' * 43])
def test_invalid_tokens(flow, token):
    client, _, _ = flow
    response = client.post('/auth/verify-email', json={'token': token})
    assert response.status_code in {400, 422}
    assert token not in response.text

def test_unverified_session_rejected_and_existing_account_works(flow, accounts):
    client, _, _ = flow
    user, headers = accounts()
    assert client.get('/auth/me', headers=headers).status_code == 200
    with Session(get_engine()) as session:
        stored = session.get(User, user['id'])
        stored.email_verified = False
        session.commit()
    assert client.get('/auth/me', headers=headers).status_code == 401

def test_verification_rate_limit(flow, monkeypatch):
    from app.config import get_settings
    client, email, _ = flow
    monkeypatch.setattr(get_settings(), 'auth_requests_per_minute', 1)
    assert client.post('/auth/resend-verification', json={'email': email}).status_code == 202
    assert client.post('/auth/resend-verification', json={'email': email}).status_code == 429

def test_0008_preserves_existing_users_and_sessions():
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    from sqlalchemy.schema import CreateSchema, DropSchema
    schema = 'dmi_verification_' + uuid4().hex
    with get_engine().begin() as conn:
        conn.execute(CreateSchema(schema))
        try:
            conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
            config.attributes['connection'] = conn
            command.upgrade(config, '0007')
            conn.execute(text("INSERT INTO users(id,email,password_hash,role) VALUES (88,'existing@example.com','preserved-hash','ADMIN')"))
            conn.execute(text("INSERT INTO auth_sessions(token_hash,user_id,csrf_token,expires_at) VALUES ('preserved-session',88,'preserved-csrf',now()+interval '1 hour')"))
            before = dict(conn.execute(text('SELECT * FROM users WHERE id=88')).mappings().one())
            command.upgrade(config, '0008')
            after = dict(conn.execute(text('SELECT * FROM users WHERE id=88')).mappings().one())
            assert after.pop('email_verified') is True
            assert after == before
            assert conn.scalar(text("SELECT count(*) FROM auth_sessions WHERE user_id=88")) == 1
            command.downgrade(config, '0007')
            assert dict(conn.execute(text('SELECT * FROM users WHERE id=88')).mappings().one()) == before
            command.upgrade(config, '0008')
        finally:
            conn.execute(text('SET LOCAL search_path TO public'))
            conn.execute(DropSchema(schema, cascade=True))
