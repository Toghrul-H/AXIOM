"""Student-only, privacy-preserving Study Partner API."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.responses import Response
from sqlalchemy import and_, delete, exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import student_user, utc
from app.auth_models import User
from app.database import get_session
from app.models import Topic
from app.study_partner_models import StudyPartnerAvailability, StudyPartnerBlock, StudyPartnerChatReceipt, StudyPartnerMessage, StudyPartnerMessageAttachment, StudyPartnerMessageReaction, StudyPartnerProfile, StudyPartnerRequest, StudyPartnerTopic
from app.study_partner_schemas import AvailabilitySlot, StudyPartnerBlockCreate, StudyPartnerBlockRead, StudyPartnerChatRead, StudyPartnerChatReadWrite, StudyPartnerChatReceiptRead, StudyPartnerChatTypingWrite, StudyPartnerMessageCreate, StudyPartnerMessageAttachmentRead, StudyPartnerMessageReactionWrite, StudyPartnerMessageRead, StudyPartnerProfileRead, StudyPartnerProfileWrite, StudyPartnerPublicRead, StudyPartnerRequestCreate, StudyPartnerRequestRead, StudyPartnerTopicRead
from app.services.course_material_storage import MaterialValidationError, StorageConfigurationError, StorageOperationError, is_inline_preview_type, required_private_storage, validate_material_upload
from app.config import get_settings
from app.services.notifications import create_notification


router = APIRouter(tags=["Study Partner"])
DB = Annotated[Session, Depends(get_session)]
Student = Annotated[User, Depends(student_user)]
Id = Annotated[int, Path(gt=0)]

REQUEST_COOLDOWN = timedelta(hours=24)
TYPING_TTL = timedelta(seconds=12)
CHAT_ATTACHMENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "text/plain",
    "text/markdown",
}


def now() -> datetime:
    return datetime.now(timezone.utc)


def notify_student(
    session: Session,
    *,
    recipient_user_id: int,
    actor_user_id: int,
    kind: str,
    dedupe_key: str,
    title: str,
    resource_id: int,
) -> None:
    recipient = session.get(User, recipient_user_id)
    if (
        recipient is None
        or recipient.role != "STUDENT"
        or not recipient.is_active
        or not recipient.email_verified
        or recipient.is_legacy
    ):
        return
    create_notification(
        session,
        recipient_user_id=recipient_user_id,
        actor_user_id=actor_user_id,
        kind=kind,
        dedupe_key=dedupe_key,
        payload={"title": title, "resource_id": resource_id},
        link="/student/study-partner",
    )


def topic_rows(session: Session, profile_user_id: int) -> list[tuple[StudyPartnerTopic, Topic]]:
    return list(
        session.execute(
            select(StudyPartnerTopic, Topic)
            .join(Topic, Topic.id == StudyPartnerTopic.topic_id)
            .where(StudyPartnerTopic.profile_user_id == profile_user_id)
            .order_by(Topic.sort_order, Topic.id, StudyPartnerTopic.purpose)
        )
    )


def topic_read(row: tuple[StudyPartnerTopic, Topic]) -> dict:
    preference, topic = row
    return {"topic_id": topic.id, "purpose": preference.purpose, "name": topic.name, "slug": topic.slug}


def availability_rows(session: Session, profile_user_id: int) -> list[StudyPartnerAvailability]:
    return list(
        session.scalars(
            select(StudyPartnerAvailability)
            .where(StudyPartnerAvailability.profile_user_id == profile_user_id)
            .order_by(StudyPartnerAvailability.weekday, StudyPartnerAvailability.start_minute, StudyPartnerAvailability.end_minute)
        )
    )


def profile_read(session: Session, profile: StudyPartnerProfile | None) -> dict:
    if profile is None:
        return {"exists": False}
    return {
        "exists": True,
        "display_name": profile.display_name,
        "is_participating": profile.is_participating,
        "is_discoverable": profile.is_discoverable,
        "study_format": profile.study_format,
        "introduction": profile.introduction,
        "topics": [topic_read(row) for row in topic_rows(session, profile.user_id)],
        "availability": [
            {"weekday": slot.weekday, "start_minute": slot.start_minute, "end_minute": slot.end_minute}
            for slot in availability_rows(session, profile.user_id)
        ],
    }


def require_participating_profile(session: Session, user_id: int) -> StudyPartnerProfile:
    profile = session.get(StudyPartnerProfile, user_id)
    if profile is None or not profile.is_participating:
        raise HTTPException(409, "Enable Study Partner participation to continue")
    return profile


def validate_topics(session: Session, payload: StudyPartnerProfileWrite) -> None:
    topic_ids = {item.topic_id for item in payload.topics}
    if not topic_ids:
        return
    found = set(session.scalars(select(Topic.id).where(Topic.id.in_(topic_ids))))
    if found != topic_ids:
        raise HTTPException(422, "One or more topics are not available")


def cancel_pending_between(session: Session, first_user_id: int, second_user_id: int | None = None) -> None:
    where = [StudyPartnerRequest.status == "PENDING"]
    if second_user_id is None:
        where.append(or_(StudyPartnerRequest.requester_user_id == first_user_id, StudyPartnerRequest.recipient_user_id == first_user_id))
    else:
        low, high = sorted((first_user_id, second_user_id))
        where.extend((StudyPartnerRequest.pair_low_user_id == low, StudyPartnerRequest.pair_high_user_id == high))
    session.execute(update(StudyPartnerRequest).where(*where).values(status="CANCELLED", resolved_at=now(), updated_at=now()))


def cancel_active_between(session: Session, first_user_id: int, second_user_id: int) -> None:
    """A block ends any active connection without deleting its private history."""
    low, high = sorted((first_user_id, second_user_id))
    session.execute(
        update(StudyPartnerRequest)
        .where(
            StudyPartnerRequest.pair_low_user_id == low,
            StudyPartnerRequest.pair_high_user_id == high,
            StudyPartnerRequest.status.in_(("PENDING", "ACCEPTED")),
        )
        .values(status="CANCELLED", resolved_at=now(), updated_at=now())
    )


def is_blocked(session: Session, first_user_id: int, second_user_id: int) -> bool:
    return bool(
        session.scalar(
            select(StudyPartnerBlock.blocker_user_id).where(
                or_(
                    and_(StudyPartnerBlock.blocker_user_id == first_user_id, StudyPartnerBlock.blocked_user_id == second_user_id),
                    and_(StudyPartnerBlock.blocker_user_id == second_user_id, StudyPartnerBlock.blocked_user_id == first_user_id),
                )
            )
        )
    )


def lock_pair(session: Session, first_user_id: int, second_user_id: int) -> None:
    """Serialize pair creation/blocking without relying on a cross-table constraint."""
    session.execute(
        select(User.id)
        .where(User.id.in_(sorted((first_user_id, second_user_id))))
        .order_by(User.id)
        .with_for_update()
    )


def formats_compatible(first: str, second: str) -> bool:
    return first == "EITHER" or second == "EITHER" or first == second


def availability_compatible(first: list[StudyPartnerAvailability], second: list[StudyPartnerAvailability]) -> bool:
    return any(
        one.weekday == two.weekday and one.start_minute < two.end_minute and two.start_minute < one.end_minute
        for one in first
        for two in second
    )


def public_partner_read_from_data(
    actor_topics: set[tuple[int, str]],
    actor_availability: list[StudyPartnerAvailability],
    partner: StudyPartnerProfile,
    partner_rows: list[tuple[StudyPartnerTopic, Topic]],
    partner_availability: list[StudyPartnerAvailability],
) -> dict:
    actor_wants = {topic_id for topic_id, purpose in actor_topics if purpose == "WANT_TO_STUDY"}
    actor_helps = {topic_id for topic_id, purpose in actor_topics if purpose == "CAN_HELP"}
    shared = [row for row in partner_rows if row[0].purpose == "WANT_TO_STUDY" and row[0].topic_id in actor_wants]
    complementary = [
        row
        for row in partner_rows
        if (row[0].purpose == "CAN_HELP" and row[0].topic_id in actor_wants)
        or (row[0].purpose == "WANT_TO_STUDY" and row[0].topic_id in actor_helps)
    ]
    return {
        "profile_id": partner.user_id,
        "display_name": partner.display_name,
        "introduction": partner.introduction,
        "study_format": partner.study_format,
        "shared_study_topics": [topic_read(row) for row in shared],
        "complementary_topics": [topic_read(row) for row in complementary],
        "has_compatible_availability": availability_compatible(
            actor_availability, partner_availability
        ),
    }


def public_partner_read(session: Session, actor_profile: StudyPartnerProfile, partner: StudyPartnerProfile) -> dict:
    return public_partner_read_from_data(
        {(entry.topic_id, entry.purpose) for entry, _ in topic_rows(session, actor_profile.user_id)},
        availability_rows(session, actor_profile.user_id),
        partner,
        topic_rows(session, partner.user_id),
        availability_rows(session, partner.user_id),
    )


def partner_rank(actor_profile: StudyPartnerProfile, partner: StudyPartnerProfile, public: dict) -> tuple[int, int, int, int, int]:
    """Deterministic, server-only ordering; no score is disclosed to students."""
    format_match = 2 if actor_profile.study_format == partner.study_format else 1
    return (
        -len(public["shared_study_topics"]),
        -len(public["complementary_topics"]),
        -format_match,
        -int(public["has_compatible_availability"]),
        partner.user_id,
    )


def request_read(session: Session, request: StudyPartnerRequest, actor_id: int) -> dict:
    counterpart_id = request.recipient_user_id if request.requester_user_id == actor_id else request.requester_user_id
    counterpart = session.get(StudyPartnerProfile, counterpart_id)
    return {
        "id": request.id,
        "status": request.status,
        "created_at": request.created_at,
        "updated_at": request.updated_at,
        "resolved_at": request.resolved_at,
        "counterpart": {"profile_id": counterpart_id, "display_name": counterpart.display_name if counterpart else "Study partner"},
    }


def owned_request_or_404(session: Session, request_id: int, actor_id: int) -> StudyPartnerRequest:
    request = session.get(StudyPartnerRequest, request_id)
    if request is None or actor_id not in {request.requester_user_id, request.recipient_user_id}:
        raise HTTPException(404, "Study request not found")
    return request


def accessible_chat_or_404(session: Session, request_id: int, actor_id: int) -> StudyPartnerRequest:
    request = session.get(StudyPartnerRequest, request_id)
    if request is None or actor_id not in {request.requester_user_id, request.recipient_user_id}:
        raise HTTPException(404, "Conversation not available")
    counterpart_id = request.recipient_user_id if request.requester_user_id == actor_id else request.requester_user_id
    if request.status != "ACCEPTED" or is_blocked(session, actor_id, counterpart_id):
        raise HTTPException(404, "Conversation not available")
    return request


def message_reads(
    session: Session,
    messages: list[StudyPartnerMessage],
    actor_id: int,
    counterpart_last_read_message_id: int | None = None,
) -> list[dict]:
    if not messages:
        return []
    message_ids = [message.id for message in messages]
    counts: dict[int, list[dict]] = defaultdict(list)
    for message_id, emoji, count in session.execute(
        select(
            StudyPartnerMessageReaction.message_id,
            StudyPartnerMessageReaction.emoji,
            func.count(StudyPartnerMessageReaction.id),
        )
        .where(StudyPartnerMessageReaction.message_id.in_(message_ids))
        .group_by(StudyPartnerMessageReaction.message_id, StudyPartnerMessageReaction.emoji)
        .order_by(StudyPartnerMessageReaction.message_id, StudyPartnerMessageReaction.emoji)
    ):
        counts[message_id].append({"emoji": emoji, "count": count, "reacted_by_me": False})
    mine = set(
        session.execute(
            select(StudyPartnerMessageReaction.message_id, StudyPartnerMessageReaction.emoji).where(
                StudyPartnerMessageReaction.message_id.in_(message_ids),
                StudyPartnerMessageReaction.user_id == actor_id,
            )
        )
    )
    for message_id, reactions in counts.items():
        for reaction in reactions:
            reaction["reacted_by_me"] = (message_id, reaction["emoji"]) in mine
    attachments: dict[int, list[dict]] = defaultdict(list)
    for attachment in session.scalars(
        select(StudyPartnerMessageAttachment)
        .where(StudyPartnerMessageAttachment.message_id.in_(message_ids))
        .order_by(StudyPartnerMessageAttachment.id)
    ):
        if attachment.message_id is not None:
            attachments[attachment.message_id].append(attachment_read(attachment))
    reply_ids = {message.reply_to_message_id for message in messages if message.reply_to_message_id is not None}
    replies = {
        reply.id: reply
        for reply in session.scalars(
            select(StudyPartnerMessage).where(
                StudyPartnerMessage.id.in_(reply_ids),
                StudyPartnerMessage.request_id == messages[0].request_id,
            )
        )
    } if reply_ids else {}
    return [
        {
            "id": message.id,
            "sender_user_id": message.sender_user_id,
            "content": message.content,
            "created_at": message.created_at,
            "reply_to_message_id": message.reply_to_message_id,
            "reply_to": (
                {"id": reply.id, "sender_user_id": reply.sender_user_id, "content": reply.content}
                if (reply := replies.get(message.reply_to_message_id)) is not None
                else None
            ),
            "reactions": counts.get(message.id, []),
            "attachments": attachments.get(message.id, []),
            "seen_by_counterpart": bool(
                message.sender_user_id == actor_id
                and counterpart_last_read_message_id is not None
                and message.id <= counterpart_last_read_message_id
            ),
        }
        for message in messages
    ]


def message_read(
    session: Session,
    message: StudyPartnerMessage,
    actor_id: int,
    counterpart_last_read_message_id: int | None = None,
) -> dict:
    return message_reads(session, [message], actor_id, counterpart_last_read_message_id)[0]


def chat_message_or_404(session: Session, request_id: int, message_id: int, actor_id: int) -> StudyPartnerMessage:
    accessible_chat_or_404(session, request_id, actor_id)
    message = session.scalar(
        select(StudyPartnerMessage).where(
            StudyPartnerMessage.id == message_id,
            StudyPartnerMessage.request_id == request_id,
        )
    )
    if message is None:
        raise HTTPException(404, "Message not available")
    return message


def counterpart_id(request: StudyPartnerRequest, actor_id: int) -> int:
    return request.recipient_user_id if request.requester_user_id == actor_id else request.requester_user_id


def receipt_for(
    session: Session,
    request_id: int,
    user_id: int,
    *,
    create: bool = False,
) -> StudyPartnerChatReceipt | None:
    receipt = session.get(StudyPartnerChatReceipt, {"request_id": request_id, "user_id": user_id})
    if receipt is None and create:
        receipt = StudyPartnerChatReceipt(request_id=request_id, user_id=user_id)
        session.add(receipt)
        session.flush()
    return receipt


def attachment_read(attachment: StudyPartnerMessageAttachment) -> dict:
    return {
        "id": attachment.id,
        "filename": attachment.original_filename,
        "media_type": attachment.media_type,
        "size_bytes": attachment.size_bytes,
        "is_inline_preview": is_inline_preview_type(attachment.media_type),
    }


def _attachment_storage_or_unavailable():
    try:
        return required_private_storage()
    except StorageConfigurationError:
        raise HTTPException(503, "Chat attachment storage is unavailable") from None


async def _read_attachment_upload(request: Request) -> bytes:
    limit = get_settings().study_partner_chat_max_attachment_bytes
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise HTTPException(413, "Chat attachment exceeds the configured size limit")
    return bytes(body)


def attachment_for_actor_or_404(
    session: Session,
    request_id: int,
    attachment_id: int,
    actor_id: int,
) -> StudyPartnerMessageAttachment:
    accessible_chat_or_404(session, request_id, actor_id)
    attachment = session.scalar(
        select(StudyPartnerMessageAttachment).where(
            StudyPartnerMessageAttachment.id == attachment_id,
            StudyPartnerMessageAttachment.request_id == request_id,
        )
    )
    if attachment is None or (
        attachment.message_id is None and attachment.uploader_user_id != actor_id
    ):
        raise HTTPException(404, "Attachment not available")
    return attachment


def serve_attachment(attachment: StudyPartnerMessageAttachment, *, inline: bool) -> Response:
    storage = _attachment_storage_or_unavailable()
    try:
        content = storage.get(
            attachment.storage_key,
            max_bytes=get_settings().study_partner_chat_max_attachment_bytes,
        )
    except StorageOperationError:
        raise HTTPException(502, "Chat attachment is unavailable") from None
    if (
        len(content) != attachment.size_bytes
        or sha256(content).hexdigest() != attachment.sha256
    ):
        raise HTTPException(502, "Chat attachment is unavailable")
    media_type = attachment.media_type
    if inline and media_type == "text/markdown":
        media_type = "text/plain; charset=utf-8"
    elif media_type.startswith("text/"):
        media_type = f"{media_type}; charset=utf-8"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'{"inline" if inline else "attachment"}; filename="{attachment.original_filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


def upload_chat_attachment_bytes(
    session: Session,
    request_id: int,
    actor_id: int,
    filename: str | None,
    claimed_media_type: str | None,
    content: bytes,
) -> StudyPartnerMessageAttachment:
    accessible_chat_or_404(session, request_id, actor_id)
    try:
        file = validate_material_upload(
            filename,
            claimed_media_type,
            content,
            max_bytes=get_settings().study_partner_chat_max_attachment_bytes,
        )
    except MaterialValidationError as error:
        raise HTTPException(422, str(error)) from None
    if file.media_type not in CHAT_ATTACHMENT_TYPES:
        raise HTTPException(422, "Unsupported chat attachment type")
    storage = _attachment_storage_or_unavailable()
    key = storage.new_key()
    try:
        stored_key = storage.put(key, file) or key
    except StorageOperationError:
        try:
            storage.delete(key)
        except StorageOperationError:
            pass
        raise HTTPException(502, "Chat attachment storage is temporarily unavailable") from None
    attachment = StudyPartnerMessageAttachment(
        request_id=request_id,
        uploader_user_id=actor_id,
        original_filename=file.filename,
        storage_key=stored_key,
        media_type=file.media_type,
        size_bytes=file.size_bytes,
        sha256=file.sha256,
    )
    session.add(attachment)
    try:
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        try:
            storage.delete(stored_key)
        except StorageOperationError:
            pass
        raise HTTPException(503, "Chat attachment could not be saved; retry it") from None
    session.refresh(attachment)
    return attachment


def counterpart_last_read_message_id(
    session: Session, request_id: int, actor_id: int
) -> int | None:
    request = session.get(StudyPartnerRequest, request_id)
    if request is None:
        return None
    receipt = receipt_for(session, request_id, counterpart_id(request, actor_id))
    return receipt.last_read_message_id if receipt else None


@router.get("/study-partner/me", response_model=StudyPartnerProfileRead)
def get_my_profile(session: DB, actor: Student):
    return profile_read(session, session.get(StudyPartnerProfile, actor.id))


@router.put("/study-partner/me", response_model=StudyPartnerProfileRead)
def put_my_profile(payload: StudyPartnerProfileWrite, session: DB, actor: Student):
    validate_topics(session, payload)
    profile = session.get(StudyPartnerProfile, actor.id)
    was_participating = profile.is_participating if profile else False
    if profile is None:
        profile = StudyPartnerProfile(user_id=actor.id, display_name=payload.display_name)
        session.add(profile)
    profile.display_name = payload.display_name
    profile.is_participating = payload.is_participating
    profile.is_discoverable = payload.is_discoverable
    profile.study_format = payload.study_format
    profile.introduction = payload.introduction
    session.execute(delete(StudyPartnerTopic).where(StudyPartnerTopic.profile_user_id == actor.id))
    session.execute(delete(StudyPartnerAvailability).where(StudyPartnerAvailability.profile_user_id == actor.id))
    session.add_all(
        StudyPartnerTopic(profile_user_id=actor.id, topic_id=item.topic_id, purpose=item.purpose)
        for item in payload.topics
    )
    session.add_all(
        StudyPartnerAvailability(profile_user_id=actor.id, weekday=item.weekday, start_minute=item.start_minute, end_minute=item.end_minute)
        for item in payload.availability
    )
    # Pausing is deliberate: it immediately withdraws all outstanding invitations,
    # while accepted/declined history remains intact.
    if was_participating and not payload.is_participating:
        cancel_pending_between(session, actor.id)
    session.commit()
    session.refresh(profile)
    return profile_read(session, profile)


@router.get("/study-partner/partners", response_model=list[StudyPartnerPublicRead])
def partners(
    session: DB,
    actor: Student,
    topic_id: Annotated[list[int], Query()] = [],
    study_format: Literal["ONLINE", "IN_PERSON", "EITHER"] | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    actor_profile = require_participating_profile(session, actor.id)
    blocked_by_actor = exists(select(StudyPartnerBlock.blocker_user_id).where(StudyPartnerBlock.blocker_user_id == actor.id, StudyPartnerBlock.blocked_user_id == StudyPartnerProfile.user_id))
    actor_blocked = exists(select(StudyPartnerBlock.blocker_user_id).where(StudyPartnerBlock.blocker_user_id == StudyPartnerProfile.user_id, StudyPartnerBlock.blocked_user_id == actor.id))
    statement = (
        select(StudyPartnerProfile)
        .join(User, User.id == StudyPartnerProfile.user_id)
        .where(
            StudyPartnerProfile.user_id != actor.id,
            StudyPartnerProfile.is_participating.is_(True),
            StudyPartnerProfile.is_discoverable.is_(True),
            User.role == "STUDENT",
            User.is_active.is_(True),
            User.email_verified.is_(True),
            User.is_legacy.is_(False),
            ~blocked_by_actor,
            ~actor_blocked,
        )
    )
    if topic_id:
        statement = statement.where(
            exists(select(StudyPartnerTopic.id).where(StudyPartnerTopic.profile_user_id == StudyPartnerProfile.user_id, StudyPartnerTopic.topic_id.in_(topic_id)))
        )
    if study_format and study_format != "EITHER":
        statement = statement.where(StudyPartnerProfile.study_format.in_((study_format, "EITHER")))
    candidates = list(session.scalars(statement))
    candidate_ids = [partner.user_id for partner in candidates]
    if not candidate_ids:
        return []
    rows_by_partner: dict[int, list[tuple[StudyPartnerTopic, Topic]]] = defaultdict(list)
    for preference, topic in session.execute(
        select(StudyPartnerTopic, Topic)
        .join(Topic, Topic.id == StudyPartnerTopic.topic_id)
        .where(StudyPartnerTopic.profile_user_id.in_(candidate_ids))
        .order_by(Topic.sort_order, Topic.id, StudyPartnerTopic.purpose)
    ):
        rows_by_partner[preference.profile_user_id].append((preference, topic))
    availability_by_partner: dict[int, list[StudyPartnerAvailability]] = defaultdict(list)
    for slot in session.scalars(
        select(StudyPartnerAvailability)
        .where(StudyPartnerAvailability.profile_user_id.in_(candidate_ids))
        .order_by(StudyPartnerAvailability.weekday, StudyPartnerAvailability.start_minute, StudyPartnerAvailability.end_minute)
    ):
        availability_by_partner[slot.profile_user_id].append(slot)
    actor_topics = {(entry.topic_id, entry.purpose) for entry, _ in topic_rows(session, actor_profile.user_id)}
    actor_availability = availability_rows(session, actor_profile.user_id)
    ranked = []
    for partner in candidates:
        if not formats_compatible(actor_profile.study_format, partner.study_format):
            continue
        public = public_partner_read_from_data(
            actor_topics,
            actor_availability,
            partner,
            rows_by_partner[partner.user_id],
            availability_by_partner[partner.user_id],
        )
        ranked.append((partner_rank(actor_profile, partner, public), public))
    ranked.sort(key=lambda item: item[0])
    return [public for _, public in ranked[offset : offset + limit]]


@router.post("/study-partner/requests", response_model=StudyPartnerRequestRead, status_code=status.HTTP_201_CREATED)
def create_request(payload: StudyPartnerRequestCreate, session: DB, actor: Student):
    require_participating_profile(session, actor.id)
    if payload.recipient_profile_id == actor.id:
        raise HTTPException(422, "You cannot send a request to yourself")
    lock_pair(session, actor.id, payload.recipient_profile_id)
    recipient = session.get(StudyPartnerProfile, payload.recipient_profile_id)
    recipient_user = session.get(User, payload.recipient_profile_id)
    if (
        recipient is None
        or recipient_user is None
        or not recipient.is_participating
        or not recipient.is_discoverable
        or recipient_user.role != "STUDENT"
        or not recipient_user.is_active
        or not recipient_user.email_verified
        or recipient_user.is_legacy
        or is_blocked(session, actor.id, payload.recipient_profile_id)
    ):
        raise HTTPException(404, "Study partner not available")
    low, high = sorted((actor.id, payload.recipient_profile_id))
    latest = session.scalar(
        select(StudyPartnerRequest)
        .where(StudyPartnerRequest.pair_low_user_id == low, StudyPartnerRequest.pair_high_user_id == high)
        .order_by(StudyPartnerRequest.created_at.desc())
        .limit(1)
    )
    if latest:
        if latest.status == "PENDING":
            raise HTTPException(409, "A study request is already pending")
        if latest.status == "ACCEPTED":
            raise HTTPException(409, "You are already study partners")
        if latest.resolved_at and now() - utc(latest.resolved_at) < REQUEST_COOLDOWN:
            raise HTTPException(429, "Please wait before sending another study request")
    request = StudyPartnerRequest(
        requester_user_id=actor.id,
        recipient_user_id=payload.recipient_profile_id,
        pair_low_user_id=low,
        pair_high_user_id=high,
    )
    session.add(request)
    try:
        session.flush()
        notify_student(
            session,
            recipient_user_id=request.recipient_user_id,
            actor_user_id=actor.id,
            kind="STUDY_PARTNER_REQUEST_RECEIVED",
            dedupe_key=f"study-request:{request.id}:received",
            title="New Study Partner request",
            resource_id=request.id,
        )
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "A study request is already pending") from None
    session.refresh(request)
    return request_read(session, request, actor.id)


@router.get("/study-partner/requests", response_model=list[StudyPartnerRequestRead])
def requests(
    session: DB,
    actor: Student,
    direction: Literal["incoming", "outgoing"] = "incoming",
    request_status: Literal["PENDING", "ACCEPTED", "DECLINED", "CANCELLED"] | None = None,
):
    # Pausing cancels pending invitations, but students retain access to their
    # own accepted/declined/cancelled history and may inspect it privately.
    user_column = StudyPartnerRequest.recipient_user_id if direction == "incoming" else StudyPartnerRequest.requester_user_id
    statement = select(StudyPartnerRequest).where(user_column == actor.id).order_by(StudyPartnerRequest.updated_at.desc(), StudyPartnerRequest.id.desc())
    if request_status:
        statement = statement.where(StudyPartnerRequest.status == request_status)
    return [request_read(session, item, actor.id) for item in session.scalars(statement)]


@router.get("/study-partner/chats", response_model=list[StudyPartnerChatRead])
def chats(session: DB, actor: Student):
    accepted = list(
        session.scalars(
            select(StudyPartnerRequest)
            .where(
                StudyPartnerRequest.status == "ACCEPTED",
                or_(StudyPartnerRequest.requester_user_id == actor.id, StudyPartnerRequest.recipient_user_id == actor.id),
            )
            .order_by(StudyPartnerRequest.id)
        )
    )
    accessible = [
        request
        for request in accepted
        if not is_blocked(
            session,
            actor.id,
            request.recipient_user_id if request.requester_user_id == actor.id else request.requester_user_id,
        )
    ]
    if not accessible:
        return []
    request_ids = [request.id for request in accessible]
    receipts = {
        (receipt.request_id, receipt.user_id): receipt
        for receipt in session.scalars(
            select(StudyPartnerChatReceipt).where(
                StudyPartnerChatReceipt.request_id.in_(request_ids)
            )
        )
    }
    counterpart_ids = {
        request.recipient_user_id if request.requester_user_id == actor.id else request.requester_user_id
        for request in accessible
    }
    profiles = {
        profile.user_id: profile
        for profile in session.scalars(select(StudyPartnerProfile).where(StudyPartnerProfile.user_id.in_(counterpart_ids)))
    }
    latest_by_request: dict[int, StudyPartnerMessage] = {}
    for message in session.scalars(
        select(StudyPartnerMessage)
        .where(StudyPartnerMessage.request_id.in_(request_ids))
        .order_by(StudyPartnerMessage.request_id, StudyPartnerMessage.created_at.desc(), StudyPartnerMessage.id.desc())
    ):
        latest_by_request.setdefault(message.request_id, message)
    result = []
    for request in accessible:
        other_user_id = counterpart_id(request, actor.id)
        profile = profiles.get(other_user_id)
        latest = latest_by_request.get(request.id)
        receipt = receipts.get((request.id, actor.id))
        unread_statement = select(func.count(StudyPartnerMessage.id)).where(
            StudyPartnerMessage.request_id == request.id,
            StudyPartnerMessage.sender_user_id != actor.id,
        )
        if receipt and receipt.last_read_message_id is not None:
            unread_statement = unread_statement.where(
                StudyPartnerMessage.id > receipt.last_read_message_id
            )
        other_receipt = receipts.get((request.id, other_user_id))
        result.append(
            {
                "request_id": request.id,
                "counterpart": {"profile_id": other_user_id, "display_name": profile.display_name if profile else "Study partner"},
                "last_message_preview": latest.content.replace("\n", " ")[:160] if latest else None,
                "last_message_at": latest.created_at if latest else None,
                "unread_count": session.scalar(unread_statement) or 0,
                "counterpart_typing": bool(
                    other_receipt
                    and other_receipt.typing_expires_at
                    and utc(other_receipt.typing_expires_at) > now()
                ),
            }
        )
    return sorted(result, key=lambda item: (utc(item["last_message_at"]) if item["last_message_at"] else datetime.min.replace(tzinfo=timezone.utc), item["request_id"]), reverse=True)


@router.get("/study-partner/chats/{request_id}/messages", response_model=list[StudyPartnerMessageRead])
def chat_messages(
    request_id: Id,
    session: DB,
    actor: Student,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    request = accessible_chat_or_404(session, request_id, actor.id)
    messages = list(
        session.scalars(
            select(StudyPartnerMessage)
            .where(StudyPartnerMessage.request_id == request_id)
            .order_by(StudyPartnerMessage.created_at, StudyPartnerMessage.id)
            .offset(offset)
            .limit(limit)
        )
    )
    other_receipt = receipt_for(session, request_id, counterpart_id(request, actor.id))
    return message_reads(
        session,
        messages,
        actor.id,
        other_receipt.last_read_message_id if other_receipt else None,
    )


@router.post(
    "/study-partner/chats/{request_id}/read",
    response_model=StudyPartnerChatReceiptRead,
)
def mark_chat_read(
    request_id: Id,
    payload: StudyPartnerChatReadWrite,
    session: DB,
    actor: Student,
):
    accessible_chat_or_404(session, request_id, actor.id)
    message = session.scalar(
        select(StudyPartnerMessage).where(
            StudyPartnerMessage.id == payload.last_message_id,
            StudyPartnerMessage.request_id == request_id,
        )
    )
    if message is None:
        raise HTTPException(404, "Message not available")
    receipt = receipt_for(session, request_id, actor.id, create=True)
    if receipt.last_read_message_id is None or message.id > receipt.last_read_message_id:
        receipt.last_read_message_id = message.id
        session.commit()
    return {"last_read_message_id": receipt.last_read_message_id}


@router.post("/study-partner/chats/{request_id}/typing")
def update_chat_typing(
    request_id: Id,
    payload: StudyPartnerChatTypingWrite,
    session: DB,
    actor: Student,
):
    accessible_chat_or_404(session, request_id, actor.id)
    receipt = receipt_for(session, request_id, actor.id, create=True)
    receipt.typing_expires_at = now() + TYPING_TTL if payload.is_typing else None
    session.commit()
    return {"is_typing": payload.is_typing}


@router.post(
    "/study-partner/chats/{request_id}/attachments",
    response_model=StudyPartnerMessageAttachmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_chat_attachment(
    request_id: Id,
    request: Request,
    session: DB,
    actor: Student,
):
    content = await _read_attachment_upload(request)
    return attachment_read(
        upload_chat_attachment_bytes(
            session,
            request_id,
            actor.id,
            request.headers.get("X-Chat-Filename"),
            request.headers.get("Content-Type"),
            content,
        )
    )


@router.delete("/study-partner/chats/{request_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pending_chat_attachment(
    request_id: Id,
    attachment_id: Id,
    session: DB,
    actor: Student,
):
    attachment = attachment_for_actor_or_404(session, request_id, attachment_id, actor.id)
    if attachment.message_id is not None or attachment.uploader_user_id != actor.id:
        raise HTTPException(404, "Attachment not available")
    storage = _attachment_storage_or_unavailable()
    try:
        storage.delete(attachment.storage_key)
    except StorageOperationError:
        raise HTTPException(502, "Chat attachment storage is temporarily unavailable") from None
    session.delete(attachment)
    try:
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(503, "Chat attachment deletion could not be completed; retry it") from None


@router.get("/study-partner/chats/{request_id}/attachments/{attachment_id}/download")
def download_chat_attachment(request_id: Id, attachment_id: Id, session: DB, actor: Student):
    return serve_attachment(
        attachment_for_actor_or_404(session, request_id, attachment_id, actor.id),
        inline=False,
    )


@router.get("/study-partner/chats/{request_id}/attachments/{attachment_id}/preview")
def preview_chat_attachment(request_id: Id, attachment_id: Id, session: DB, actor: Student):
    attachment = attachment_for_actor_or_404(session, request_id, attachment_id, actor.id)
    if not is_inline_preview_type(attachment.media_type):
        raise HTTPException(422, "This attachment type cannot be previewed inline")
    return serve_attachment(attachment, inline=True)


@router.post("/study-partner/chats/{request_id}/messages", response_model=StudyPartnerMessageRead, status_code=status.HTTP_201_CREATED)
def send_chat_message(request_id: Id, payload: StudyPartnerMessageCreate, session: DB, actor: Student):
    request = accessible_chat_or_404(session, request_id, actor.id)
    other_user_id = counterpart_id(request, actor.id)
    lock_pair(session, actor.id, other_user_id)
    accessible_chat_or_404(session, request_id, actor.id)
    if payload.reply_to_message_id is not None:
        reply = session.scalar(
            select(StudyPartnerMessage).where(
                StudyPartnerMessage.id == payload.reply_to_message_id,
                StudyPartnerMessage.request_id == request_id,
            )
        )
        if reply is None:
            raise HTTPException(422, "Reply message is not available in this conversation")
    attachments: list[StudyPartnerMessageAttachment] = []
    if payload.attachment_ids:
        attachments = list(
            session.scalars(
                select(StudyPartnerMessageAttachment)
                .where(
                    StudyPartnerMessageAttachment.id.in_(payload.attachment_ids),
                    StudyPartnerMessageAttachment.request_id == request_id,
                    StudyPartnerMessageAttachment.uploader_user_id == actor.id,
                    StudyPartnerMessageAttachment.message_id.is_(None),
                )
                .with_for_update()
            )
        )
        if {attachment.id for attachment in attachments} != set(payload.attachment_ids):
            raise HTTPException(422, "One or more chat attachments are not available")
    message = StudyPartnerMessage(
        request_id=request_id,
        sender_user_id=actor.id,
        content=payload.content,
        reply_to_message_id=payload.reply_to_message_id,
    )
    session.add(message)
    session.flush()
    for attachment in attachments:
        attachment.message_id = message.id
    notify_student(
        session,
        recipient_user_id=other_user_id,
        actor_user_id=actor.id,
        kind="STUDY_PARTNER_CHAT_MESSAGE",
        dedupe_key=f"study-chat-message:{message.id}",
        title="New Study Partner message",
        resource_id=request_id,
    )
    session.commit()
    session.refresh(message)
    other_receipt = receipt_for(session, request_id, other_user_id)
    return message_read(
        session,
        message,
        actor.id,
        other_receipt.last_read_message_id if other_receipt else None,
    )


@router.post(
    "/study-partner/chats/{request_id}/messages/{message_id}/reactions",
    response_model=StudyPartnerMessageRead,
)
def add_message_reaction(
    request_id: Id,
    message_id: Id,
    payload: StudyPartnerMessageReactionWrite,
    session: DB,
    actor: Student,
):
    message = chat_message_or_404(session, request_id, message_id, actor.id)
    exists_for_user = session.scalar(
        select(StudyPartnerMessageReaction.id).where(
            StudyPartnerMessageReaction.message_id == message.id,
            StudyPartnerMessageReaction.user_id == actor.id,
            StudyPartnerMessageReaction.emoji == payload.emoji,
        )
    )
    if exists_for_user is None:
        session.add(
            StudyPartnerMessageReaction(
                message_id=message.id,
                user_id=actor.id,
                emoji=payload.emoji,
            )
        )
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
    return message_read(
        session,
        message,
        actor.id,
        counterpart_last_read_message_id(session, request_id, actor.id),
    )


@router.delete(
    "/study-partner/chats/{request_id}/messages/{message_id}/reactions",
    response_model=StudyPartnerMessageRead,
)
def remove_message_reaction(
    request_id: Id,
    message_id: Id,
    payload: StudyPartnerMessageReactionWrite,
    session: DB,
    actor: Student,
):
    message = chat_message_or_404(session, request_id, message_id, actor.id)
    session.execute(
        delete(StudyPartnerMessageReaction).where(
            StudyPartnerMessageReaction.message_id == message.id,
            StudyPartnerMessageReaction.user_id == actor.id,
            StudyPartnerMessageReaction.emoji == payload.emoji,
        )
    )
    session.commit()
    return message_read(
        session,
        message,
        actor.id,
        counterpart_last_read_message_id(session, request_id, actor.id),
    )


def transition_request(session: Session, request_id: int, actor_id: int, action: Literal["accept", "decline", "cancel"]) -> StudyPartnerRequest:
    request = owned_request_or_404(session, request_id, actor_id)
    if action in {"accept", "decline"} and request.recipient_user_id != actor_id:
        raise HTTPException(404, "Study request not found")
    if action == "cancel" and request.requester_user_id != actor_id:
        raise HTTPException(404, "Study request not found")
    # Use the same ordered participant locks as request creation and blocking.
    # This prevents a status transition and a simultaneous block from acquiring
    # user foreign-key locks in opposite orders during notification creation.
    lock_pair(session, request.requester_user_id, request.recipient_user_id)
    next_status = {"accept": "ACCEPTED", "decline": "DECLINED", "cancel": "CANCELLED"}[action]
    result = session.execute(
        update(StudyPartnerRequest)
        .where(StudyPartnerRequest.id == request_id, StudyPartnerRequest.status == "PENDING")
        .values(status=next_status, resolved_at=now(), updated_at=now())
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        session.rollback()
        raise HTTPException(409, "This study request is no longer pending")
    recipient_user_id = (
        request.requester_user_id
        if action in {"accept", "decline"}
        else request.recipient_user_id
    )
    next_kind = f"STUDY_PARTNER_REQUEST_{next_status}"
    next_title = {
        "ACCEPTED": "Study Partner request accepted",
        "DECLINED": "Study Partner request declined",
        "CANCELLED": "Study Partner request cancelled",
    }[next_status]
    notify_student(
        session,
        recipient_user_id=recipient_user_id,
        actor_user_id=actor_id,
        kind=next_kind,
        dedupe_key=f"study-request:{request.id}:{next_status.lower()}",
        title=next_title,
        resource_id=request.id,
    )
    session.commit()
    session.refresh(request)
    return request


@router.post("/study-partner/requests/{request_id}/accept", response_model=StudyPartnerRequestRead)
def accept_request(request_id: Id, session: DB, actor: Student):
    return request_read(session, transition_request(session, request_id, actor.id, "accept"), actor.id)


@router.post("/study-partner/requests/{request_id}/decline", response_model=StudyPartnerRequestRead)
def decline_request(request_id: Id, session: DB, actor: Student):
    return request_read(session, transition_request(session, request_id, actor.id, "decline"), actor.id)


@router.post("/study-partner/requests/{request_id}/cancel", response_model=StudyPartnerRequestRead)
def cancel_request(request_id: Id, session: DB, actor: Student):
    return request_read(session, transition_request(session, request_id, actor.id, "cancel"), actor.id)


@router.post("/study-partner/blocks", response_model=StudyPartnerBlockRead, status_code=status.HTTP_201_CREATED)
def create_block(payload: StudyPartnerBlockCreate, session: DB, actor: Student):
    if payload.blocked_user_id == actor.id:
        raise HTTPException(422, "You cannot block yourself")
    lock_pair(session, actor.id, payload.blocked_user_id)
    target = session.get(User, payload.blocked_user_id)
    target_profile = session.get(StudyPartnerProfile, payload.blocked_user_id)
    is_known_counterpart = bool(
        session.scalar(
            select(StudyPartnerRequest.id)
            .where(
                or_(
                    and_(StudyPartnerRequest.requester_user_id == actor.id, StudyPartnerRequest.recipient_user_id == payload.blocked_user_id),
                    and_(StudyPartnerRequest.requester_user_id == payload.blocked_user_id, StudyPartnerRequest.recipient_user_id == actor.id),
                )
            )
            .limit(1)
        )
    )
    if (
        target is None
        or target_profile is None
        or not ((target_profile.is_participating and target_profile.is_discoverable) or is_known_counterpart)
        or target.role != "STUDENT"
        or not target.is_active
        or not target.email_verified
        or target.is_legacy
    ):
        raise HTTPException(404, "Study partner not available")
    block = session.get(StudyPartnerBlock, {"blocker_user_id": actor.id, "blocked_user_id": payload.blocked_user_id})
    if block is not None:
        return {"blocked_user_id": block.blocked_user_id, "created_at": block.created_at}
    block = StudyPartnerBlock(blocker_user_id=actor.id, blocked_user_id=payload.blocked_user_id)
    session.add(block)
    cancel_active_between(session, actor.id, payload.blocked_user_id)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.get(StudyPartnerBlock, {"blocker_user_id": actor.id, "blocked_user_id": payload.blocked_user_id})
        if existing is None:
            raise
        return {"blocked_user_id": existing.blocked_user_id, "created_at": existing.created_at}
    session.refresh(block)
    return {"blocked_user_id": block.blocked_user_id, "created_at": block.created_at}


@router.delete("/study-partner/blocks/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_block(user_id: Id, session: DB, actor: Student):
    session.execute(delete(StudyPartnerBlock).where(StudyPartnerBlock.blocker_user_id == actor.id, StudyPartnerBlock.blocked_user_id == user_id))
    session.commit()
