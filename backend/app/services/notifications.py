"""Transaction-safe primitives for private in-application notifications."""

import base64
import json
import re
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from urllib.parse import urlsplit

from fastapi import HTTPException
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.auth_models import User
from app.notification_models import Notification


_KIND = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_DEDUPE_KEY = re.compile(r"[A-Za-z0-9:_-]{1,160}\Z")
_PAYLOAD_KEYS = {
    "title",
    "body",
    "subject",
    "label",
    "resource_type",
    "resource_id",
    "status",
    "actor_display_name",
}
_SENSITIVE_KEY = re.compile(
    r"(?:email|neptun|token|password|secret|availability|message|chat|content)",
    re.IGNORECASE,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def eligible_student_ids(session: Session) -> list[int]:
    """Recipients for globally visible student-facing course material."""
    return list(
        session.scalars(
            select(User.id).where(
                User.role == "STUDENT",
                User.is_active.is_(True),
                User.email_verified.is_(True),
                User.is_legacy.is_(False),
            )
        )
    )


def validate_link(link: str) -> str:
    if not isinstance(link, str) or len(link) > 240 or not link.startswith("/"):
        raise ValueError("Notification links must be internal application paths")
    parsed = urlsplit(link)
    if (
        link.startswith("//")
        or "\\" in link
        or parsed.scheme
        or parsed.netloc
        or any(ord(character) < 32 for character in link)
    ):
        raise ValueError("Notification links must be safe internal application paths")
    return link


def validate_payload(payload: Mapping[str, object]) -> dict[str, str | int | bool | None]:
    if not isinstance(payload, Mapping) or not payload:
        raise ValueError("Notification payload must contain display-safe metadata")
    if set(payload) - _PAYLOAD_KEYS:
        raise ValueError("Notification payload contains unsupported metadata")
    result: dict[str, str | int | bool | None] = {}
    for key, value in payload.items():
        if _SENSITIVE_KEY.search(key):
            raise ValueError("Notification payload may not contain sensitive metadata")
        if not isinstance(value, (str, int, bool)) and value is not None:
            raise ValueError("Notification payload values must be simple display-safe values")
        if isinstance(value, str):
            if len(value) > 500 or any(ord(character) < 32 for character in value):
                raise ValueError("Notification payload text is invalid")
        result[key] = value
    try:
        encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        raise ValueError("Notification payload is not JSON-safe") from error
    if len(encoded.encode("utf-8")) > 2_000:
        raise ValueError("Notification payload is too large")
    return result


def _validate_create(
    recipient_user_id: int,
    actor_user_id: int | None,
    kind: str,
    dedupe_key: str,
    payload: Mapping[str, object],
    link: str,
) -> tuple[dict[str, str | int | bool | None], str]:
    if not isinstance(recipient_user_id, int) or recipient_user_id <= 0:
        raise ValueError("Notification recipient is invalid")
    if actor_user_id is not None and (not isinstance(actor_user_id, int) or actor_user_id <= 0):
        raise ValueError("Notification actor is invalid")
    if not isinstance(kind, str) or not _KIND.fullmatch(kind):
        raise ValueError("Notification kind is invalid")
    if not isinstance(dedupe_key, str) or not _DEDUPE_KEY.fullmatch(dedupe_key):
        raise ValueError("Notification deduplication key is invalid")
    return validate_payload(payload), validate_link(link)


def create_notification(
    session: Session,
    *,
    recipient_user_id: int,
    actor_user_id: int | None = None,
    kind: str,
    dedupe_key: str,
    payload: Mapping[str, object],
    link: str,
) -> tuple[Notification, bool]:
    """Add one notification without committing the caller's transaction."""
    clean_payload, clean_link = _validate_create(
        recipient_user_id, actor_user_id, kind, dedupe_key, payload, link
    )
    existing = session.scalar(
        select(Notification).where(
            Notification.recipient_user_id == recipient_user_id,
            Notification.dedupe_key == dedupe_key,
        )
    )
    if existing is not None:
        return existing, False
    values = {
        "recipient_user_id": recipient_user_id,
        "actor_user_id": actor_user_id,
        "kind": kind,
        "dedupe_key": dedupe_key,
        "payload": clean_payload,
        "link": clean_link,
    }
    dialect = session.get_bind().dialect.name
    if dialect in {"postgresql", "sqlite"}:
        insert = postgresql_insert if dialect == "postgresql" else sqlite_insert
        inserted_id = session.scalar(
            insert(Notification)
            .values(**values)
            .on_conflict_do_nothing(
                index_elements=("recipient_user_id", "dedupe_key")
            )
            .returning(Notification.id)
        )
        if inserted_id is not None:
            notification = session.get(Notification, inserted_id)
            if notification is not None:
                return notification, True
        existing = session.scalar(
            select(Notification).where(
                Notification.recipient_user_id == recipient_user_id,
                Notification.dedupe_key == dedupe_key,
            )
        )
        if existing is not None:
            return existing, False
        raise RuntimeError("Notification insertion did not return a record")
    try:
        with session.begin_nested():
            notification = Notification(**values)
            session.add(notification)
            session.flush()
        return notification, True
    except IntegrityError:
        existing = session.scalar(
            select(Notification).where(
                Notification.recipient_user_id == recipient_user_id,
                Notification.dedupe_key == dedupe_key,
            )
        )
        if existing is None:
            raise
        return existing, False


def create_notifications(
    session: Session,
    *,
    recipient_user_ids: Iterable[int],
    actor_user_id: int | None = None,
    kind: str,
    dedupe_key: str,
    payload: Mapping[str, object],
    link: str,
) -> list[tuple[Notification, bool]]:
    """Idempotently fan out one safe notification without committing."""
    recipient_values = list(recipient_user_ids)
    if any(not isinstance(recipient, int) or recipient <= 0 for recipient in recipient_values):
        raise ValueError("Notification recipient is invalid")
    recipients = sorted(set(recipient_values))
    if not recipients:
        return []
    clean_payload, clean_link = _validate_create(
        recipients[0], actor_user_id, kind, dedupe_key, payload, link
    )
    existing = {
        item.recipient_user_id: item
        for item in session.scalars(
            select(Notification).where(
                Notification.recipient_user_id.in_(recipients),
                Notification.dedupe_key == dedupe_key,
            )
        )
    }
    missing = [recipient for recipient in recipients if recipient not in existing]
    inserted_recipients: set[int] = set()
    dialect = session.get_bind().dialect.name
    if missing and dialect in {"postgresql", "sqlite"}:
        insert = postgresql_insert if dialect == "postgresql" else sqlite_insert
        rows = session.execute(
            insert(Notification)
            .values(
                [
                    {
                        "recipient_user_id": recipient,
                        "actor_user_id": actor_user_id,
                        "kind": kind,
                        "dedupe_key": dedupe_key,
                        "payload": clean_payload,
                        "link": clean_link,
                    }
                    for recipient in missing
                ]
            )
            .on_conflict_do_nothing(
                index_elements=("recipient_user_id", "dedupe_key")
            )
            .returning(Notification.recipient_user_id)
        ).all()
        inserted_recipients = {row[0] for row in rows}
        existing = {
            item.recipient_user_id: item
            for item in session.scalars(
                select(Notification).where(
                    Notification.recipient_user_id.in_(recipients),
                    Notification.dedupe_key == dedupe_key,
                )
            )
        }
    else:
        for recipient in missing:
            notification, created = create_notification(
                session,
                recipient_user_id=recipient,
                actor_user_id=actor_user_id,
                kind=kind,
                dedupe_key=dedupe_key,
                payload=clean_payload,
                link=clean_link,
            )
            existing[recipient] = notification
            if created:
                inserted_recipients.add(recipient)
    if len(existing) != len(recipients):
        raise RuntimeError("Notification fan-out did not return every recipient")
    return [
        (existing[recipient], recipient in inserted_recipients)
        for recipient in recipients
    ]


def encode_cursor(notification: Notification) -> str:
    timestamp = notification.created_at
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    raw = f"{timestamp.isoformat()}|{notification.id}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode("utf-8")
        timestamp, identifier = raw.rsplit("|", 1)
        value = datetime.fromisoformat(timestamp)
        notification_id = int(identifier)
        if value.tzinfo is None or notification_id <= 0:
            raise ValueError
        return value, notification_id
    except (UnicodeDecodeError, ValueError) as error:
        raise HTTPException(422, "Invalid notification cursor") from error


def list_notifications(
    session: Session, recipient_user_id: int, *, limit: int, cursor: str | None
) -> tuple[list[Notification], str | None]:
    statement = select(Notification).where(Notification.recipient_user_id == recipient_user_id)
    if cursor:
        timestamp, notification_id = decode_cursor(cursor)
        statement = statement.where(
            or_(
                Notification.created_at < timestamp,
                (Notification.created_at == timestamp) & (Notification.id < notification_id),
            )
        )
    rows = list(
        session.scalars(
            statement.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit + 1)
        )
    )
    page = rows[:limit]
    return page, encode_cursor(page[-1]) if len(rows) > limit and page else None


def unread_count(session: Session, recipient_user_id: int) -> int:
    return int(
        session.scalar(
            select(func.count(Notification.id)).where(
                Notification.recipient_user_id == recipient_user_id,
                Notification.read_at.is_(None),
            )
        )
        or 0
    )


def mark_read(session: Session, recipient_user_id: int, notification_id: int) -> Notification:
    notification = session.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_user_id == recipient_user_id,
        )
    )
    if notification is None:
        raise HTTPException(404, "Notification not found")
    if notification.read_at is None:
        notification.read_at = utc_now()
    return notification


def mark_all_read(session: Session, recipient_user_id: int) -> int:
    result = session.execute(
        update(Notification)
        .where(
            Notification.recipient_user_id == recipient_user_id,
            Notification.read_at.is_(None),
        )
        .values(read_at=utc_now())
    )
    return int(result.rowcount or 0)
