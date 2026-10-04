import os
from pathlib import Path
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema
from app.main import app
from app.database import get_engine
from app.auth_models import User, EmailVerification
from app.auth_schemas import Credentials
from app.scripts.system_accounts import create_protected_admin, create_system_admin, protect_existing
from app.services.email_verification import issue_verification
from conftest import TEST_PASSWORD

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS') != '1', reason='Requires local PostgreSQL')]

def test_additional_system_admin_and_duplicate_rejection(accounts):
    accounts('ADMIN')
    email = f'owner-{uuid4().hex}@example.com'
    # Roll back the entire fixture; no permanent operator account is created.
    with Session(get_engine()) as session:
        try:
            credentials = Credentials(email='  ' + email.upper() + '  ', password=TEST_PASSWORD)
            uid = create_system_admin(session, credentials)
            user = session.get(User, uid)
            assert user.email == email and user.role == 'ADMIN'
            assert user.is_system_managed and user.email_verified and user.is_active
            from app.auth import passwords
            assert passwords.verify(TEST_PASSWORD, user.password_hash)
            with pytest.raises(ValueError, match='already registered'):
                create_system_admin(session, credentials)
            with pytest.raises(ValueError, match='already exists'):
                create_protected_admin(session, Credentials(email=f'other-{uuid4().hex}@example.com', password=TEST_PASSWORD))
        finally:
            session.rollback()

def test_additional_admin_cli_requires_confirmation(monkeypatch, capsys):
    from app.scripts import system_accounts
    monkeypatch.setattr('sys.argv', ['system_accounts', 'create-system-admin'])
    answers = iter(['operator@example.com', 'cancel'])
    monkeypatch.setattr('builtins.input', lambda prompt: next(answers))
    monkeypatch.setattr(system_accounts, 'getpass', lambda prompt: TEST_PASSWORD)
    monkeypatch.setattr(system_accounts, 'create_system_admin', lambda *args: pytest.fail('Must not create without confirmation'))
    with pytest.raises(SystemExit, match='Cancelled'):
        system_accounts.main()
    output = capsys.readouterr().out
    assert 'additional ADMIN allowed' in output and TEST_PASSWORD not in output

@pytest.mark.parametrize('manager_role', ['ADMIN', 'LECTURER'])
def test_hidden_from_listing_search_and_direct_management(accounts, manager_role):
    _, headers = accounts(manager_role)
    target, _ = accounts('DEMONSTRATOR')
    with Session(get_engine()) as session, session.begin():
        assert not session.get(User, target['id']).is_system_managed
        protect_existing(session, target['id'], target['email'])
    with TestClient(app) as client:
        for query in ['', target['email']]:
            response = client.get('/users', params={'q': query, 'limit': 100}, headers=headers)
            assert response.status_code == 200
            assert target['id'] not in [u['id'] for u in response.json()]
        for action, body in [('role', {'role': 'STUDENT'}), ('status', {'is_active': False}), ('status', {'is_active': True})]:
            response = client.post(f"/users/{target['id']}/{action}", json=body, headers=headers)
            assert response.status_code == 403
            assert target['email'] not in response.text
    with Session(get_engine()) as session:
        user = session.get(User, target['id'])
        assert user.role == 'DEMONSTRATOR' and user.is_active

@pytest.mark.parametrize('role', ['ADMIN', 'STUDENT'])
def test_protected_account_authenticates_with_actual_role(accounts, role):
    user, headers = accounts(role)
    with Session(get_engine()) as session, session.begin():
        stored = session.get(User, user['id'])
        old_hash = stored.password_hash
        stored.email_verified = False
        issue_verification(session, stored, lambda email, token: None)
        protect_existing(session, user['id'], user['email'])
        assert stored.password_hash == old_hash and stored.role == role
        assert stored.email_verified and stored.is_system_managed
        assert session.get(EmailVerification, stored.id) is None
    with TestClient(app) as client:
        assert client.get('/auth/me', headers=headers).status_code == 401
        response = client.post('/auth/login', json={'email': user['email'], 'password': TEST_PASSWORD})
        assert response.status_code == 200
        assert response.json()['user']['role'] == role
        assert 'is_system_managed' not in response.json()['user']
        assert client.get('/users').status_code == (200 if role == 'ADMIN' else 403)
        assert client.get('/questions').status_code == (200 if role == 'ADMIN' else 403)
        assert client.get('/student/progress/me').status_code == (200 if role == 'STUDENT' else 403)

def test_public_registration_cannot_request_protection(accounts):
    accounts()  # Resets the shared rate limiter.
    with TestClient(app) as client:
        for payload in [
            {'email': 'untrusted@gmail.com', 'password': TEST_PASSWORD},
            {'email': 'untrusted@inf.elte.hu', 'password': TEST_PASSWORD, 'is_system_managed': True},
        ]:
            assert client.post('/auth/register', json=payload).status_code == 422

def test_private_protect_refuses_mismatch_and_inactive(accounts):
    user, _ = accounts()
    with Session(get_engine()) as session, session.begin():
        with pytest.raises(ValueError, match='mismatch'):
            protect_existing(session, user['id'], 'wrong@example.com')
        stored = session.get(User, user['id'])
        assert not stored.is_system_managed
        stored.is_active = False
        with pytest.raises(ValueError, match='inactive'):
            protect_existing(session, user['id'], user['email'])

def test_0009_migration_and_private_first_admin_provisioning():
    schema = 'dmi_system_' + uuid4().hex
    with get_engine().begin() as conn:
        conn.execute(CreateSchema(schema))
        try:
            conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
            config.attributes['connection'] = conn
            command.upgrade(config, '0008')
            conn.execute(text("INSERT INTO users(id,email,role) VALUES (88,'old@example.com','STUDENT')"))
            before = dict(conn.execute(text('SELECT * FROM users WHERE id=88')).mappings().one())
            command.upgrade(config, '0009')
            after = dict(conn.execute(text('SELECT * FROM users WHERE id=88')).mappings().one())
            assert after.pop('is_system_managed') is False
            assert before == after
            with Session(conn, join_transaction_mode='create_savepoint') as session, session.begin():
                credentials = Credentials(email='private-owner@example.com', password=TEST_PASSWORD)
                uid = create_protected_admin(session, credentials)
                admin = session.get(User, uid)
                assert admin.role == 'ADMIN' and admin.email_verified and admin.is_system_managed
                from app.auth import passwords
                assert passwords.verify(TEST_PASSWORD, admin.password_hash)
                with pytest.raises(ValueError, match='already exists'):
                    create_protected_admin(session, Credentials(email='second@example.com', password=TEST_PASSWORD))
            command.downgrade(config, '0008')
            assert dict(conn.execute(text('SELECT * FROM users WHERE id=88')).mappings().one()) == before
            command.upgrade(config, '0009')
        finally:
            conn.execute(text('SET LOCAL search_path TO public'))
            conn.execute(DropSchema(schema, cascade=True))
