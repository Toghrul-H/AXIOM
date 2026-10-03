"""Token lifecycle; delivery is injected separately and never exposed through the API."""
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
import re
from typing import Protocol
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth import digest
from app.auth_models import User, EmailVerification

class VerificationDelivery(Protocol):
    def __call__(self, email: str, token: str) -> None: ...

def get_verification_delivery() -> VerificationDelivery:
    from app.services.smtp_delivery import send_verification_email
    return send_verification_email

def issue_verification(session: Session, user: User, deliver: VerificationDelivery) -> None:
    # Caller holds the user lock (or has just inserted the user).
    now = datetime.now(timezone.utc)
    old = session.get(EmailVerification, user.id)
    if old and old.created_at > now - timedelta(seconds=60):
        return  # Per-account cooldown, including across processes.
    token = token_urlsafe(32)
    if old is None:
        old = EmailVerification(user_id=user.id)
        session.add(old)
    old.token_hash = digest(token)
    old.created_at = now
    old.expires_at = now + timedelta(hours=1)
    session.flush()
    deliver(user.email, token)

def verify_email(session: Session, token: str) -> None:
    invalid = HTTPException(400, 'Invalid or expired verification token')
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
        raise invalid
    token_hash = digest(token)
    user_id = session.scalar(select(EmailVerification.user_id).where(EmailVerification.token_hash == token_hash))
    if user_id is None:
        raise invalid
    user = session.scalar(select(User).where(User.id == user_id).with_for_update())
    record = session.get(EmailVerification, user_id, populate_existing=True)
    if (not user or not user.is_active or user.is_legacy or user.email_verified
        or not record or record.token_hash != token_hash
        or record.expires_at <= datetime.now(timezone.utc)):
        raise invalid
    user.email_verified = True
    session.delete(record)
    session.commit()
