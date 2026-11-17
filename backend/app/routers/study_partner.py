"""Student-only, privacy-preserving Study Partner API."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import and_, delete, exists, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import student_user, utc
from app.auth_models import User
from app.database import get_session
from app.models import Topic
from app.study_partner_models import StudyPartnerAvailability, StudyPartnerBlock, StudyPartnerProfile, StudyPartnerRequest, StudyPartnerTopic
from app.study_partner_schemas import AvailabilitySlot, StudyPartnerBlockCreate, StudyPartnerBlockRead, StudyPartnerProfileRead, StudyPartnerProfileWrite, StudyPartnerPublicRead, StudyPartnerRequestCreate, StudyPartnerRequestRead, StudyPartnerTopicRead


router = APIRouter(tags=["Study Partner"])
DB = Annotated[Session, Depends(get_session)]
Student = Annotated[User, Depends(student_user)]
Id = Annotated[int, Path(gt=0)]

REQUEST_COOLDOWN = timedelta(hours=24)


def now() -> datetime:
    return datetime.now(timezone.utc)


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


def transition_request(session: Session, request_id: int, actor_id: int, action: Literal["accept", "decline", "cancel"]) -> StudyPartnerRequest:
    request = owned_request_or_404(session, request_id, actor_id)
    if action in {"accept", "decline"} and request.recipient_user_id != actor_id:
        raise HTTPException(404, "Study request not found")
    if action == "cancel" and request.requester_user_id != actor_id:
        raise HTTPException(404, "Study request not found")
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
