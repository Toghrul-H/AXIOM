import json
import os
import ssl
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import Settings, get_settings
from app.database import get_engine
from app.auth_models import User, EmailVerification
from app.main import app
from app.services import brevo_delivery
from app.services.email_delivery import DeliveryUnavailable
from app.services.email_verification import get_verification_delivery
from test_email_verification import flow, register

@pytest.fixture
def transport(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, 'email_delivery_provider', 'brevo')
    monkeypatch.setattr(settings, 'brevo_api_key', SecretStr('test-api-secret'))
    monkeypatch.setattr(settings, 'smtp_host', '')
    monkeypatch.setattr(settings, 'smtp_password', SecretStr(''))
    factory = MagicMock()
    factory.return_value.getresponse.return_value.status = 201
    monkeypatch.setattr(brevo_delivery.http.client, 'HTTPSConnection', factory)
    return factory

def test_success_and_provider_selection(transport, caplog):
    assert get_verification_delivery() is brevo_delivery.send_verification_email
    get_verification_delivery()('recipient@inf.elte.hu', 'private-token')
    args, kwargs = transport.call_args
    assert args == ('api.brevo.com',)
    assert kwargs['timeout'] == 10
    assert kwargs['context'].verify_mode == ssl.CERT_REQUIRED and kwargs['context'].check_hostname
    args, kwargs = transport.return_value.request.call_args
    assert args == ('POST', '/v3/smtp/email')
    assert kwargs['headers']['api-key'] == 'test-api-secret'
    data = json.loads(kwargs['body'])
    assert data['sender'] == {'email': 'sender@example.com', 'name': 'AXIOM'}
    assert data['to'] == [{'email': 'recipient@inf.elte.hu'}]
    assert '/verify-email?token=private-token' in data['textContent']
    assert 'http://127.0.0.1:3000' in data['textContent']
    assert not caplog.text
    transport.return_value.close.assert_called_once()

@pytest.mark.parametrize('status', [302, 400, 401, 403, 429, 500])
def test_http_failure_sanitized(transport, caplog, status):
    transport.return_value.getresponse.return_value.status = status
    transport.return_value.getresponse.return_value.read.return_value = b'test-api-secret private-token recipient@inf.elte.hu'
    with pytest.raises(DeliveryUnavailable):
        brevo_delivery.send_verification_email('recipient@inf.elte.hu', 'private-token')
    assert f'provider=brevo status={status}' in caplog.text
    for secret in ['test-api-secret', 'private-token', 'recipient@inf.elte.hu']:
        assert secret not in caplog.text
    transport.return_value.getresponse.return_value.read.assert_not_called()
    assert all(record.exc_info is None for record in caplog.records)

@pytest.mark.parametrize('error, category', [(OSError('private-token'), 'network_or_protocol_failure'),
    (TimeoutError('test-api-secret'), 'timeout'), (ssl.SSLError('test-api-secret'), 'tls_failure')])
def test_network_failure(transport, caplog, error, category):
    transport.return_value.request.side_effect = error
    with pytest.raises(DeliveryUnavailable):
        brevo_delivery.send_verification_email('recipient@inf.elte.hu', 'private-token')
    assert category in caplog.text
    assert 'test-api-secret' not in caplog.text and 'private-token' not in caplog.text

@pytest.mark.parametrize('field,value', [('email_from_address', ''), ('email_from_name', ''),
    ('frontend_base_url', ''), ('brevo_api_key', SecretStr(''))])
def test_missing_config(transport, monkeypatch, field, value):
    monkeypatch.setattr(get_settings(), field, value)
    with pytest.raises(DeliveryUnavailable):
        brevo_delivery.send_verification_email('recipient@inf.elte.hu', 'private-token')
    transport.assert_not_called()

def test_sender_and_provider_validation():
    for fields in [{'email_from_address': 'invalid'}, {'email_from_name': 'name\r\nInjected'},
                   {'email_delivery_provider': 'invalid'}]:
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **fields)

@pytest.mark.integration
@pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS') != '1', reason='Requires local PostgreSQL')
def test_brevo_registration_resend_failure_semantics(flow, transport):
    client, email, _ = flow
    app.dependency_overrides.pop(get_verification_delivery)
    transport.return_value.getresponse.return_value.status = 500
    assert register(client, email).status_code == 503
    with Session(get_engine()) as session:
        assert session.scalar(select(User).where(User.email == email)) is None
    transport.return_value.getresponse.return_value.status = 201
    response = register(client, email)
    assert response.status_code == 201 and response.json()['role'] == 'STUDENT'
    uid = response.json()['id']
    with Session(get_engine()) as session:
        record = session.get(EmailVerification, uid)
        record.created_at = datetime.now(timezone.utc) - timedelta(minutes=2)
        old = record.token_hash
        session.commit()
    transport.return_value.getresponse.return_value.status = 429
    failed = client.post('/auth/resend-verification', json={'email': email})
    unknown = client.post('/auth/resend-verification', json={'email': 'unknown@inf.elte.hu'})
    assert failed.status_code == unknown.status_code == 202 and failed.json() == unknown.json()
    with Session(get_engine()) as session:
        assert not session.get(User, uid).email_verified
        assert session.get(EmailVerification, uid).token_hash == old
