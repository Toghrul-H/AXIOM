from uuid import uuid4
import os
import pytest
from fastapi import Response
from sqlalchemy import delete
from sqlalchemy.orm import Session
from app.auth import COOKIE, issue_session, passwords, _failures
from app.auth_models import User
from app.database import get_engine

# Test-only credential, never used for persistent or browser accounts.
TEST_PASSWORD = 'test-only-password-42!'

@pytest.fixture(autouse=True)
def disable_real_smtp(monkeypatch):
    # All tests, including legacy registration tests, must never contact Gmail.
    from unittest.mock import MagicMock
    import smtplib
    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, 'email_delivery_provider', 'smtp')
    # Never allow an unmocked Brevo request from any automated test.
    monkeypatch.setattr('http.client.HTTPSConnection', lambda *args, **kwargs: pytest.fail('Real HTTPS delivery forbidden in tests'))
    for key, value in {'smtp_host':'smtp.example.test', 'smtp_username':'test',
                       'email_from_address':'sender@example.com',
                       'frontend_base_url':'http://127.0.0.1:3000'}.items():
        monkeypatch.setattr(settings, key, value)
    from pydantic import SecretStr
    monkeypatch.setattr(settings, 'smtp_password', SecretStr('test-only-smtp-secret'))
    monkeypatch.setattr(settings, 'smtp_use_tls', True)
    monkeypatch.setattr(settings, 'smtp_port', 587)
    for name in ['SMTP', 'SMTP_SSL']:
        factory = MagicMock()
        factory.return_value.__enter__.return_value.send_message.return_value = {}
        monkeypatch.setattr(smtplib, name, factory)

def pytest_sessionstart(session):
    # Integration fixtures write/delete data. Never run them against a deployment.
    if os.getenv('RUN_POSTGRES_TESTS') == '1':
        if get_engine().url.host not in {'localhost', '127.0.0.1', '::1'}:
            raise pytest.UsageError('PostgreSQL integration tests require a local database. Configure the connection privately before running tests.')

@pytest.fixture
def accounts():
    ids=[]
    _failures.clear()
    def create(role='STUDENT',active=True):
        with Session(get_engine()) as session:
            user=User(email=f'test-{uuid4().hex}@example.com',password_hash=passwords.hash(TEST_PASSWORD),role=role,is_active=active)
            session.add(user); session.commit()
            ids.append(user.id)
            response=Response()
            csrf=issue_session(session,user,response)
            cookie=response.headers['set-cookie'].split(';')[0]
            return {'id':user.id,'email':user.email,'role':role}, {'Cookie':cookie,'X-CSRF-Token':csrf}
    yield create
    with Session(get_engine()) as session:
        session.execute(delete(User).where(User.id.in_(ids)))
        session.commit()
    _failures.clear()
