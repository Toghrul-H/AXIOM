from datetime import datetime, timedelta, timezone
import asyncio
import sys

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException
from sqlalchemy import JSON, MetaData, UniqueConstraint, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth import _failures, digest, issue_session, limit_password_reset, passwords
from app.auth_models import AuthSession, PasswordResetOutbox, PasswordResetToken, User
from app.auth_schemas import PasswordResetInput
from app.database import Base, get_session
from app.routers import auth as auth_router
from app.services.email_delivery import DeliveryUnavailable
from app.services.password_reset import (
    OUTBOX_LEASE,
    _claim_outbox,
    issue_password_reset,
    process_password_reset_outbox_once,
    reset_password,
)


def sqlite_metadata() -> MetaData:
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        clone = table.to_metadata(metadata)
        for column in clone.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()
        for constraint in clone.constraints:
            if (
                isinstance(constraint, UniqueConstraint)
                and constraint.name
                in {"uq_question_options_position", "uq_quiz_questions_position"}
            ):
                constraint.deferrable = None
                constraint.initially = None
    return metadata


@pytest.fixture
def reset_setup():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sqlite_metadata().create_all(engine)
    session = Session(engine)
    users = {
        "eligible": User(
            email="eligible@example.com",
            password_hash=passwords.hash("old-password-42!"),
            role="STUDENT",
            email_verified=True,
        ),
        "inactive": User(
            email="inactive@example.com",
            password_hash=passwords.hash("old-password-42!"),
            role="STUDENT",
            is_active=False,
            email_verified=True,
        ),
        "unverified": User(
            email="unverified@example.com",
            password_hash=passwords.hash("old-password-42!"),
            role="STUDENT",
            email_verified=False,
        ),
        "managed": User(
            email="managed@example.com",
            password_hash=passwords.hash("old-password-42!"),
            role="ADMIN",
            is_system_managed=True,
            email_verified=True,
        ),
    }
    session.add_all(users.values())
    session.commit()
    yield session, users, engine
    session.close()
    engine.dispose()


@pytest.fixture
def cipher():
    return Fernet(Fernet.generate_key())


def _token(session: Session, user_id: int, cipher: Fernet) -> str:
    outbox = session.scalar(
        select(PasswordResetOutbox).where(PasswordResetOutbox.user_id == user_id)
    )
    assert outbox is not None
    return cipher.decrypt(outbox.token_ciphertext.encode("ascii")).decode("ascii")


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="The local Windows test sandbox cannot create ASGI socket pairs; run on Linux CI.",
)
def test_forgot_password_http_parity_and_encrypted_atomic_outbox(
    reset_setup, cipher, monkeypatch
):
    session, users, _ = reset_setup
    app = FastAPI()
    app.include_router(auth_router.router)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[limit_password_reset] = lambda: False
    monkeypatch.setattr(auth_router, "get_password_reset_cipher", lambda: cipher)
    async def request_all():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return [
                await client.post("/auth/forgot-password", json={"email": email})
                for email in (
                    users["eligible"].email,
                    "unknown@example.com",
                    users["inactive"].email,
                    users["unverified"].email,
                    users["managed"].email,
                )
            ]

    responses = asyncio.run(request_all())
    assert {(response.status_code, response.json()) for response in responses} == {
        (202, auth_router.RESET_ACCEPTED)
    }
    token = _token(session, users["eligible"].id, cipher)
    token_record = session.get(PasswordResetToken, users["eligible"].id)
    outbox = session.scalar(
        select(PasswordResetOutbox).where(
            PasswordResetOutbox.user_id == users["eligible"].id
        )
    )
    assert token_record is not None and token_record.token_hash == digest(token)
    assert outbox is not None and token not in outbox.token_ciphertext


def test_worker_delivers_retries_and_removes_ciphertext_after_acceptance(
    reset_setup, cipher
):
    session, users, engine = reset_setup
    assert issue_password_reset(session, users["eligible"], cipher)
    session.commit()
    sent: list[tuple[str, str]] = []
    session_factory = lambda: Session(engine)
    now = datetime.now(timezone.utc)
    assert process_password_reset_outbox_once(
        session_factory,
        cipher,
        lambda email, token: (_ for _ in ()).throw(DeliveryUnavailable()),
        now=now,
    ) == 1
    session.expire_all()
    retry = session.scalar(
        select(PasswordResetOutbox).where(
            PasswordResetOutbox.user_id == users["eligible"].id
        )
    )
    assert retry is not None and retry.attempts == 1 and retry.claim_token is None
    assert process_password_reset_outbox_once(
        session_factory,
        cipher,
        lambda email, token: sent.append((email, token)),
        now=retry.available_at + timedelta(seconds=1),
    ) == 1
    session.expire_all()
    assert (
        session.scalar(
            select(PasswordResetOutbox).where(
                PasswordResetOutbox.user_id == users["eligible"].id
            )
        )
        is None
    )
    assert sent == [(users["eligible"].email, sent[0][1])]
    assert session.get(PasswordResetToken, users["eligible"].id).token_hash == digest(sent[0][1])


def test_claim_recovery_and_terminal_expiry_delete_encrypted_work(reset_setup, cipher):
    session, users, engine = reset_setup
    assert issue_password_reset(session, users["eligible"], cipher)
    session.commit()
    now = datetime.now(timezone.utc)
    claims = _claim_outbox(session, now, 1)
    assert len(claims) == 1
    sent: list[str] = []
    assert process_password_reset_outbox_once(
        lambda: Session(engine),
        cipher,
        lambda _email, token: sent.append(token),
        now=now + OUTBOX_LEASE + timedelta(seconds=1),
    ) == 1
    assert len(sent) == 1
    assert issue_password_reset(session, users["eligible"], cipher) is False
    session.get(PasswordResetToken, users["eligible"].id).expires_at = now - timedelta(seconds=1)
    session.add(
        PasswordResetOutbox(
            user_id=users["managed"].id,
            token_ciphertext=cipher.encrypt(b"unused").decode("ascii"),
            available_at=now,
            expires_at=now - timedelta(seconds=1),
        )
    )
    session.commit()
    process_password_reset_outbox_once(
        lambda: Session(engine),
        cipher,
        lambda _email, _token: pytest.fail("expired work must not be delivered"),
        now=now,
    )
    assert (
        session.scalar(
            select(PasswordResetOutbox).where(
                PasswordResetOutbox.user_id == users["managed"].id
            )
        )
        is None
    )


def test_reset_is_single_use_expires_and_revokes_all_sessions(reset_setup, cipher):
    session, users, _ = reset_setup
    issue_password_reset(session, users["eligible"], cipher)
    session.commit()
    token = _token(session, users["eligible"].id, cipher)
    old_hash = users["eligible"].password_hash
    issue_session(session, users["eligible"], __import__("fastapi").Response())
    assert session.query(AuthSession).filter_by(user_id=users["eligible"].id).count() == 1
    reset_password(
        session,
        token,
        "new-password-42!",
    )
    session.refresh(users["eligible"])
    assert users["eligible"].password_hash != old_hash
    assert passwords.verify("new-password-42!", users["eligible"].password_hash)
    assert session.get(PasswordResetToken, users["eligible"].id) is None
    assert (
        session.scalar(
            select(PasswordResetOutbox).where(
                PasswordResetOutbox.user_id == users["eligible"].id
            )
        )
        is None
    )
    assert session.query(AuthSession).filter_by(user_id=users["eligible"].id).count() == 0
    with pytest.raises(HTTPException, match="Invalid or expired"):
        reset_password(session, token, "another-password-42!")
    with pytest.raises(ValueError):
        PasswordResetInput(token=token, password="short")


def test_reset_expiry_and_rate_limit_remain_safe(reset_setup, cipher, monkeypatch):
    session, users, _ = reset_setup
    issue_password_reset(session, users["eligible"], cipher)
    session.commit()
    token = _token(session, users["eligible"].id, cipher)
    session.get(PasswordResetToken, users["eligible"].id).expires_at = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    )
    session.commit()
    with pytest.raises(HTTPException, match="Invalid or expired"):
        reset_password(session, token, "new-password-42!")
    from starlette.requests import Request

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "headers": [],
            "client": ("198.51.100.42", 1234),
        }
    )
    _failures.clear()
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "auth_requests_per_minute", 1)
    try:
        assert limit_password_reset(request) is False
        assert limit_password_reset(request) is True
    finally:
        _failures.clear()
