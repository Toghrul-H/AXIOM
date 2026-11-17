"""Single-use reset tokens plus an encrypted, durable email outbox."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import re
from secrets import token_urlsafe
from threading import Event
from typing import Callable, Protocol

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.auth import digest, passwords, revoke_user_sessions, utc
from app.auth_models import PasswordResetOutbox, PasswordResetToken, User
from app.config import get_settings
from app.database import get_engine
from app.services.email_delivery import DeliveryUnavailable

logger = logging.getLogger(__name__)

RESET_TTL = timedelta(minutes=30)
RESET_COOLDOWN = timedelta(seconds=60)
OUTBOX_LEASE = timedelta(minutes=2)
RETRY_BASE_SECONDS = 30
RETRY_MAX_SECONDS = 300


class ResetDelivery(Protocol):
    def __call__(self, email: str, token: str) -> None: ...


class ResetOutboxUnavailable(RuntimeError):
    """The durable queue cannot safely encrypt a new reset credential."""


SessionFactory = Callable[[], Session]


@dataclass(frozen=True)
class OutboxClaim:
    id: int
    claim_token: str


def get_password_reset_delivery() -> ResetDelivery:
    if get_settings().email_delivery_provider == "brevo":
        from app.services.brevo_delivery import send_password_reset_email

        return send_password_reset_email
    from app.services.smtp_delivery import send_password_reset_email

    return send_password_reset_email


def get_password_reset_cipher() -> Fernet:
    """Return the dedicated AEAD key without exposing it in diagnostics."""
    raw_key = get_settings().password_reset_outbox_encryption_key.get_secret_value()
    if not raw_key:
        raise ResetOutboxUnavailable("reset outbox encryption is not configured")
    try:
        return Fernet(raw_key.encode("ascii"))
    except (UnicodeEncodeError, ValueError) as error:
        raise ResetOutboxUnavailable("reset outbox encryption is invalid") from error


def eligible_for_reset(user: User | None) -> bool:
    return bool(
        user
        and user.is_active
        and user.email_verified
        and not user.is_legacy
        and not user.is_system_managed
        and user.password_hash
    )


def issue_password_reset(session: Session, user: User, cipher: Fernet) -> bool:
    """Atomically replace the token and encrypted delivery work for one user."""
    now = datetime.now(timezone.utc)
    record = session.get(PasswordResetToken, user.id)
    if record and utc(record.created_at) > now - RESET_COOLDOWN:
        return False

    token = token_urlsafe(32)
    expires_at = now + RESET_TTL
    if record is None:
        record = PasswordResetToken(user_id=user.id)
        session.add(record)
    record.token_hash = digest(token)
    record.created_at = now
    record.expires_at = expires_at

    outbox = session.scalar(
        select(PasswordResetOutbox).where(PasswordResetOutbox.user_id == user.id)
    )
    if outbox is None:
        outbox = PasswordResetOutbox(user_id=user.id)
        session.add(outbox)
    outbox.token_ciphertext = cipher.encrypt(token.encode("ascii")).decode("ascii")
    outbox.attempts = 0
    outbox.available_at = now
    outbox.expires_at = expires_at
    outbox.claim_token = None
    outbox.claimed_at = None
    outbox.last_error_category = None
    session.flush()
    return True


def reset_password(session: Session, token: str, password: str) -> None:
    invalid = HTTPException(400, "Invalid or expired reset token")
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise invalid
    token_hash = digest(token)
    record = session.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == token_hash)
        .with_for_update()
    )
    if record is None:
        raise invalid
    user = session.scalar(
        select(User).where(User.id == record.user_id).with_for_update()
    )
    if (
        not eligible_for_reset(user)
        or record.token_hash != token_hash
        or utc(record.expires_at) <= datetime.now(timezone.utc)
    ):
        raise invalid
    user.password_hash = passwords.hash(password)
    revoke_user_sessions(session, user.id)
    # A consumed link is terminal: remove any queued encrypted copy atomically.
    session.execute(
        delete(PasswordResetOutbox).where(PasswordResetOutbox.user_id == user.id)
    )
    session.delete(record)
    session.commit()


def _claim_outbox(
    session: Session,
    now: datetime,
    batch_size: int,
) -> list[OutboxClaim]:
    session.execute(delete(PasswordResetOutbox).where(PasswordResetOutbox.expires_at <= now))
    session.execute(
        update(PasswordResetOutbox)
        .where(
            PasswordResetOutbox.claimed_at.is_not(None),
            PasswordResetOutbox.claimed_at < now - OUTBOX_LEASE,
        )
        .values(claim_token=None, claimed_at=None)
    )
    rows = list(
        session.scalars(
            select(PasswordResetOutbox)
            .where(
                PasswordResetOutbox.available_at <= now,
                PasswordResetOutbox.expires_at > now,
                PasswordResetOutbox.claim_token.is_(None),
            )
            .order_by(PasswordResetOutbox.id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
    )
    claims: list[OutboxClaim] = []
    for row in rows:
        claim = token_urlsafe(32)
        row.claim_token = claim
        row.claimed_at = now
        claims.append(OutboxClaim(id=row.id, claim_token=claim))
    session.commit()
    return claims


def _discard_claim(session_factory: SessionFactory, claim: OutboxClaim) -> None:
    with session_factory() as session:
        row = session.scalar(
            select(PasswordResetOutbox)
            .where(
                PasswordResetOutbox.id == claim.id,
                PasswordResetOutbox.claim_token == claim.claim_token,
            )
            .with_for_update()
        )
        if row is not None:
            session.delete(row)
            session.commit()


def _retry_claim(
    session_factory: SessionFactory,
    claim: OutboxClaim,
    now: datetime,
    max_attempts: int,
    category: str,
) -> None:
    with session_factory() as session:
        row = session.scalar(
            select(PasswordResetOutbox)
            .where(
                PasswordResetOutbox.id == claim.id,
                PasswordResetOutbox.claim_token == claim.claim_token,
            )
            .with_for_update()
        )
        if row is None:
            return
        row.attempts += 1
        if utc(row.expires_at) <= now or row.attempts >= max_attempts:
            session.delete(row)
        else:
            row.available_at = now + timedelta(
                seconds=min(
                    RETRY_BASE_SECONDS * (2 ** (row.attempts - 1)),
                    RETRY_MAX_SECONDS,
                )
            )
            row.claim_token = None
            row.claimed_at = None
            row.last_error_category = category
        session.commit()


def _deliver_claim(
    session_factory: SessionFactory,
    cipher: Fernet,
    deliver: ResetDelivery,
    claim: OutboxClaim,
    now: datetime,
    max_attempts: int,
) -> None:
    with session_factory() as session:
        row = session.scalar(
            select(PasswordResetOutbox)
            .where(
                PasswordResetOutbox.id == claim.id,
                PasswordResetOutbox.claim_token == claim.claim_token,
            )
            .with_for_update()
        )
        if row is None:
            return
        if utc(row.expires_at) <= now:
            session.delete(row)
            session.commit()
            return
        try:
            token = cipher.decrypt(row.token_ciphertext.encode("ascii")).decode("ascii")
        except (InvalidToken, UnicodeDecodeError):
            session.delete(row)
            session.commit()
            logger.error("Password reset outbox discarded category=payload_unreadable")
            return
        record = session.get(PasswordResetToken, row.user_id)
        user = session.get(User, row.user_id)
        if (
            record is None
            or record.token_hash != digest(token)
            or utc(record.expires_at) <= now
            or not eligible_for_reset(user)
        ):
            session.delete(row)
            session.commit()
            return
        recipient = user.email
        # Keep the durable claim, but release the DB lock before provider I/O.
        session.commit()

    try:
        deliver(recipient, token)
    except DeliveryUnavailable:
        _retry_claim(
            session_factory,
            claim,
            datetime.now(timezone.utc),
            max_attempts,
            "delivery_unavailable",
        )
    except Exception:
        # Providers must sanitize their own diagnostics; never log token or recipient.
        logger.error("Password reset outbox retry category=unexpected_delivery_failure")
        _retry_claim(
            session_factory,
            claim,
            datetime.now(timezone.utc),
            max_attempts,
            "unexpected_delivery_failure",
        )
    else:
        # Delete only if no newer reset superseded this claim while it was sent.
        _discard_claim(session_factory, claim)


def process_password_reset_outbox_once(
    session_factory: SessionFactory,
    cipher: Fernet,
    deliver: ResetDelivery,
    *,
    now: datetime | None = None,
    batch_size: int = 10,
    max_attempts: int = 5,
) -> int:
    """Claim a bounded batch. Delivery is at-least-once after crash recovery."""
    current = utc(now) if now else datetime.now(timezone.utc)
    with session_factory() as session:
        claims = _claim_outbox(session, current, batch_size)
    for claim in claims:
        _deliver_claim(
            session_factory,
            cipher,
            deliver,
            claim,
            datetime.now(timezone.utc),
            max_attempts,
        )
    return len(claims)


class PasswordResetOutboxWorker:
    """A small per-process poller; PostgreSQL SKIP LOCKED coordinates replicas."""

    def __init__(self, stop: Event):
        self.stop = stop
        self._reported_unavailable = False

    def run_once(self) -> int:
        settings = get_settings()
        try:
            cipher = get_password_reset_cipher()
        except ResetOutboxUnavailable:
            if not self._reported_unavailable:
                logger.error(
                    "Password reset outbox unavailable category=encryption_configuration"
                )
                self._reported_unavailable = True
            return 0
        self._reported_unavailable = False
        return process_password_reset_outbox_once(
            lambda: Session(get_engine()),
            cipher,
            get_password_reset_delivery(),
            batch_size=settings.password_reset_outbox_batch_size,
            max_attempts=settings.password_reset_outbox_max_attempts,
        )

    def run(self) -> None:
        while not self.stop.is_set():
            try:
                self.run_once()
            except Exception:
                logger.error(
                    "Password reset outbox worker retry category=unexpected_worker_failure"
                )
            self.stop.wait(get_settings().password_reset_outbox_poll_seconds)
