import os
import smtplib
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import get_settings
from app.services.smtp_delivery import send_verification_email, DeliveryUnavailable
from app.services.email_verification import get_verification_delivery
from app.main import app
from app.auth_models import User, EmailVerification
from app.database import get_engine
from test_email_verification import flow, register  # Reuse isolated account cleanup.

def test_starttls_message_and_configured_link():
    send_verification_email('student@inf.elte.hu', 'test-token')
    smtp = smtplib.SMTP.return_value.__enter__.return_value
    smtplib.SMTP.assert_called_once_with('smtp.example.test', 587, timeout=10)
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with('test', 'test-only-smtp-secret')
    message = smtp.send_message.call_args.args[0]
    assert str(message['To']) == 'student@inf.elte.hu'
    assert str(message['From']) == 'AXIOM <sender@example.com>'
    assert str(message['Subject']) == 'Verify your AXIOM account'
    assert 'http://127.0.0.1:3000/verify-email?token=test-token' in message.get_content()
    assert message.get_content_charset() == 'utf-8'

def test_implicit_tls_and_no_plaintext(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, 'smtp_use_tls', False)
    with pytest.raises(DeliveryUnavailable):
        send_verification_email('student@inf.elte.hu', 'token')
    smtplib.SMTP.assert_not_called()
    monkeypatch.setattr(settings, 'smtp_port', 465)
    send_verification_email('student@inf.elte.hu', 'token')
    smtplib.SMTP_SSL.assert_called_once()

def test_smtp_error_sanitized(caplog):
    smtplib.SMTP.side_effect = smtplib.SMTPAuthenticationError(535, b'private-secret complete-token')
    with pytest.raises(DeliveryUnavailable) as error:
        send_verification_email('student@inf.elte.hu', 'complete-token')
    assert 'private-secret' not in str(error.value) + caplog.text
    assert 'complete-token' not in str(error.value) + caplog.text
    assert 'exception=SMTPAuthenticationError' in caplog.text
    assert 'smtp_code=535' in caplog.text
    assert 'SMTP authentication rejected' in caplog.text
    assert all(record.exc_info is None for record in caplog.records)

@pytest.mark.parametrize('failure, expected', [
    (TimeoutError('private-secret complete-token'), 'timed out'),
    (ConnectionRefusedError(111, 'private-secret'), 'connection refused'),
    (smtplib.SMTPRecipientsRefused({'private-recipient@example.com': (550, b'complete-token')}), 'recipient rejected'),
])
def test_safe_failure_diagnostics(caplog, failure, expected):
    smtplib.SMTP.side_effect = failure
    with pytest.raises(DeliveryUnavailable):
        send_verification_email('private-recipient@example.com', 'complete-token')
    assert expected in caplog.text and 'stage=connect' in caplog.text
    for secret in ['private-secret', 'complete-token', 'private-recipient@example.com', 'test-only-smtp-secret']:
        assert secret not in caplog.text

def test_tls_failure_stage_and_no_raw_message(caplog):
    import ssl
    smtp = smtplib.SMTP.return_value.__enter__.return_value
    smtp.starttls.side_effect = ssl.SSLCertVerificationError('private-secret')
    with pytest.raises(DeliveryUnavailable):
        send_verification_email('student@inf.elte.hu', 'complete-token')
    assert 'stage=starttls' in caplog.text
    assert 'exception=SSLCertVerificationError' in caplog.text
    assert 'private-secret' not in caplog.text
    smtp.login.assert_not_called()

@pytest.mark.integration
@pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS') != '1', reason='Requires local PostgreSQL')
def test_registration_failure_rolls_back_and_resend_failure_preserves_token(flow):
    client, email, sent = flow
    app.dependency_overrides[get_verification_delivery] = lambda: send_verification_email
    smtplib.SMTP.side_effect = smtplib.SMTPException('private-secret complete-token')
    response = register(client, email)
    assert response.status_code == 503
    assert 'private-secret' not in response.text and 'complete-token' not in response.text
    with Session(get_engine()) as session:
        assert session.scalar(select(User).where(User.email == email)) is None
    smtplib.SMTP.side_effect = None
    response = register(client, email)
    assert response.status_code == 201
    message = smtplib.SMTP.return_value.__enter__.return_value.send_message.call_args.args[0]
    assert str(message['To']) == email
    uid = response.json()['id']
    with Session(get_engine()) as session:
        record = session.get(EmailVerification, uid)
        record.created_at = datetime.now(timezone.utc) - timedelta(minutes=2)
        old_hash = record.token_hash
        session.commit()
    smtplib.SMTP.side_effect = smtplib.SMTPException('private-secret')
    failed = client.post('/auth/resend-verification', json={'email': email})
    unknown = client.post('/auth/resend-verification', json={'email': 'unknown@inf.elte.hu'})
    assert failed.status_code == unknown.status_code == 202 and failed.json() == unknown.json()
    with Session(get_engine()) as session:
        assert not session.get(User, uid).email_verified
        assert session.get(EmailVerification, uid).token_hash == old_hash
    smtplib.SMTP.side_effect = None
    assert client.post('/auth/resend-verification', json={'email': email}).status_code == 202
    with Session(get_engine()) as session:
        assert session.get(EmailVerification, uid).token_hash != old_hash
