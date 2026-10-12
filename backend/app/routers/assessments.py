from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.auth import manager_user
from app.auth_models import User
from app.database import get_session
from app.assessment_models import AssessmentConfiguration, AssessmentEvent, AssessmentRoom, AssessmentRoomGroup
from app.assessment_schemas import ConfigurationCreate, ConfigurationPatch, ConfigurationRead, ConfigurationDetail, EventWrite, EventRead, RoomWrite, RoomRead
from fastapi.responses import PlainTextResponse
from app.document_generation.service import DocumentType, render_document
from app.assessment_models import AssessmentPolicy, AssessmentGradeBoundary, AssessmentGroupDeadline
from app.assessment_policy_schemas import PolicyCode, PolicyWrite, PolicyRead, RulesWrite, RulesRead

router = APIRouter(prefix='/assessment-configurations', tags=['Semester assessment configuration'])
ROOM_EVENT_TYPES = frozenset({'MIDTERM', 'ENDTERM', 'SHORT_QUIZ_RETAKE', 'TEST_RETAKE'})
DB = Annotated[Session, Depends(get_session)]
Manager = Annotated[User, Depends(manager_user)]
Id = Annotated[int, Path(gt=0)]

@router.get('/{configuration_id}/documents/{document_type}/latex', response_class=PlainTextResponse)
def preview_latex(configuration_id: Id, document_type: DocumentType, session: DB, actor: Manager):
    return PlainTextResponse(render_document(session, configuration_id, document_type, actor))

def configuration(session, configuration_id, actor=None):
    if actor is not None:
        # Match existing management operations: recheck live privileges under lock.
        session.refresh(actor, with_for_update=True)
        if not actor.is_active or actor.role not in {'LECTURER', 'ADMIN'}:
            raise HTTPException(403, 'Account management permission required')
    query = select(AssessmentConfiguration).where(AssessmentConfiguration.id == configuration_id)
    if actor is not None:
        query = query.with_for_update()
    result = session.scalar(query)
    if result is None:
        raise HTTPException(404, 'Assessment configuration not found')
    return result

def event(session, configuration_id, event_id):
    result = session.scalar(select(AssessmentEvent).where(AssessmentEvent.id == event_id, AssessmentEvent.configuration_id == configuration_id))
    if result is None:
        raise HTTPException(404, 'Assessment event not found')
    return result

def room(session, event_id, room_id):
    result = session.scalar(select(AssessmentRoom).where(AssessmentRoom.id == room_id, AssessmentRoom.event_id == event_id))
    if result is None:
        raise HTTPException(404, 'Room assignment not found')
    return result

def touch(item, actor):
    item.updated_at = datetime.now(timezone.utc)
    item.last_modified_by_id = actor.id

def commit(session):
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, 'Conflicting semester, event, room or practice group assignment') from None

def check_grade_maximum(parent):
    maximum = parent.maximum_total_score
    if maximum is not None and any(row.minimum_score > maximum for row in parent.grade_boundaries):
        raise HTTPException(422, 'A grade threshold exceeds the configured maximum total score')

@router.get('', response_model=list[ConfigurationRead])
def list_configurations(session: DB, actor: Manager, offset: Annotated[int, Query(ge=0)] = 0, limit: Annotated[int, Query(ge=1, le=100)] = 20):
    return list(session.scalars(select(AssessmentConfiguration).order_by(AssessmentConfiguration.academic_year_start.desc(), AssessmentConfiguration.term).offset(offset).limit(limit)))

@router.post('', response_model=ConfigurationDetail, status_code=201)
def create_configuration(payload: ConfigurationCreate, session: DB, actor: Manager):
    session.refresh(actor, with_for_update=True)
    if not actor.is_active or actor.role not in {'LECTURER', 'ADMIN'}:
        raise HTTPException(403, 'Account management permission required')
    result = AssessmentConfiguration(**payload.model_dump(), last_modified_by_id=actor.id)
    session.add(result)
    commit(session)
    return result

@router.get('/{configuration_id}', response_model=ConfigurationDetail)
def get_configuration(configuration_id: Id, session: DB, actor: Manager):
    return configuration(session, configuration_id)

@router.patch('/{configuration_id}', response_model=ConfigurationDetail)
def update_configuration(configuration_id: Id, payload: ConfigurationPatch, session: DB, actor: Manager):
    result = configuration(session, configuration_id, actor)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(result, key, value)
    touch(result, actor)
    commit(session)
    return result

@router.delete('/{configuration_id}', status_code=204)
def delete_configuration(configuration_id: Id, session: DB, actor: Manager):
    session.delete(configuration(session, configuration_id, actor))
    commit(session)

@router.get('/{configuration_id}/rules', response_model=RulesRead)
def get_rules(configuration_id: Id, session: DB, actor: Manager):
    return configuration(session, configuration_id)

@router.put('/{configuration_id}/rules', response_model=RulesRead)
def update_rules(configuration_id: Id, payload: RulesWrite, session: DB, actor: Manager):
    parent = configuration(session, configuration_id, actor)
    for key, value in payload.model_dump(exclude={'grade_boundaries'}).items():
        setattr(parent, key, value)
    parent.grade_boundaries.clear()
    session.flush()
    parent.grade_boundaries = [AssessmentGradeBoundary(**row.model_dump()) for row in payload.grade_boundaries]
    check_grade_maximum(parent)
    touch(parent, actor)
    commit(session)
    return parent

@router.put('/{configuration_id}/policies/{code}', response_model=PolicyRead)
def update_policy(configuration_id: Id, code: PolicyCode, payload: PolicyWrite, session: DB, actor: Manager):
    parent = configuration(session, configuration_id, actor)
    result = session.get(AssessmentPolicy, (parent.id, code))
    if result is None:
        result = AssessmentPolicy(configuration_id=parent.id, code=code)
        session.add(result)
    for key, value in payload.model_dump().items():
        setattr(result, key, value)
    session.flush()
    session.expire(parent, ['policies'])
    check_grade_maximum(parent)
    touch(parent, actor)
    commit(session)
    return result

@router.post('/{configuration_id}/events', response_model=EventRead, status_code=201)
def create_event(configuration_id: Id, payload: EventWrite, session: DB, actor: Manager):
    parent = configuration(session, configuration_id, actor)
    fields = payload.model_dump(exclude={'group_deadlines'})
    result = AssessmentEvent(configuration_id=parent.id, **fields, last_modified_by_id=actor.id)
    result.group_deadlines = [AssessmentGroupDeadline(**row.model_dump()) for row in payload.group_deadlines]
    session.add(result)
    touch(parent, actor)
    commit(session)
    return result

@router.put('/{configuration_id}/events/{event_id}', response_model=EventRead)
def update_event(configuration_id: Id, event_id: Id, payload: EventWrite, session: DB, actor: Manager):
    parent = configuration(session, configuration_id, actor)
    result = event(session, parent.id, event_id)
    if payload.event_type not in ROOM_EVENT_TYPES and result.rooms:
        raise HTTPException(409, 'Remove room assignments before changing to an event type without room assignments')
    if payload.event_type not in {'COURSEWORK_HAND_IN', 'COURSEWORK_RETAKE_HAND_IN'} and (result.group_deadlines or any(getattr(result, k) is not None for k in ('submission_deadline_date','submission_deadline_time','submission_venue','submission_instructions'))):
        raise HTTPException(409, 'Clear submission details before changing this event type')
    extended = {'seating_plan','submission_deadline_date','submission_deadline_time','submission_venue','submission_instructions'}
    for key, value in payload.model_dump(exclude={'group_deadlines'}).items():
        if key in extended and key not in payload.model_fields_set:
            continue
        setattr(result, key, value)
    if 'group_deadlines' in payload.model_fields_set:
        result.group_deadlines.clear()
        session.flush()
        result.group_deadlines = [AssessmentGroupDeadline(**row.model_dump()) for row in payload.group_deadlines]
    touch(parent, actor)
    touch(result, actor)
    commit(session)
    return result

@router.delete('/{configuration_id}/events/{event_id}', status_code=204)
def delete_event(configuration_id: Id, event_id: Id, session: DB, actor: Manager):
    parent = configuration(session, configuration_id, actor)
    session.delete(event(session, parent.id, event_id))
    touch(parent, actor)
    commit(session)

def save_room(session, parent, assessment, actor, payload, result=None):
    if assessment.event_type not in ROOM_EVENT_TYPES:
        raise HTTPException(422, 'Room/group assignments are not supported for this event type')
    if result is None:
        result = AssessmentRoom(event_id=assessment.id, room=payload.room)
        session.add(result)
    else:
        # Flush removals first to permit replacement of the same group identifiers.
        result.groups.clear()
        session.flush()
        result.room = payload.room
    result.groups = [AssessmentRoomGroup(event_id=assessment.id, identifier=identifier) for identifier in payload.groups]
    touch(parent, actor)
    touch(assessment, actor)
    commit(session)
    return result

@router.post('/{configuration_id}/events/{event_id}/rooms', response_model=RoomRead, status_code=201)
def create_room(configuration_id: Id, event_id: Id, payload: RoomWrite, session: DB, actor: Manager):
    parent = configuration(session, configuration_id, actor)
    return save_room(session, parent, event(session, parent.id, event_id), actor, payload)

@router.put('/{configuration_id}/events/{event_id}/rooms/{room_id}', response_model=RoomRead)
def update_room(configuration_id: Id, event_id: Id, room_id: Id, payload: RoomWrite, session: DB, actor: Manager):
    parent = configuration(session, configuration_id, actor)
    assessment = event(session, parent.id, event_id)
    return save_room(session, parent, assessment, actor, payload, room(session, assessment.id, room_id))

@router.delete('/{configuration_id}/events/{event_id}/rooms/{room_id}', status_code=204)
def delete_room(configuration_id: Id, event_id: Id, room_id: Id, session: DB, actor: Manager):
    parent = configuration(session, configuration_id, actor)
    assessment = event(session, parent.id, event_id)
    session.delete(room(session, assessment.id, room_id))
    touch(parent, actor)
    touch(assessment, actor)
    commit(session)
