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

router = APIRouter(prefix='/assessment-configurations', tags=['Semester assessment configuration'])
DB = Annotated[Session, Depends(get_session)]
Manager = Annotated[User, Depends(manager_user)]
Id = Annotated[int, Path(gt=0)]

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

@router.post('/{configuration_id}/events', response_model=EventRead, status_code=201)
def create_event(configuration_id: Id, payload: EventWrite, session: DB, actor: Manager):
    parent = configuration(session, configuration_id, actor)
    result = AssessmentEvent(configuration_id=parent.id, **payload.model_dump(), last_modified_by_id=actor.id)
    session.add(result)
    touch(parent, actor)
    commit(session)
    return result

@router.put('/{configuration_id}/events/{event_id}', response_model=EventRead)
def update_event(configuration_id: Id, event_id: Id, payload: EventWrite, session: DB, actor: Manager):
    parent = configuration(session, configuration_id, actor)
    result = event(session, parent.id, event_id)
    if payload.event_type != 'ENDTERM' and result.rooms:
        raise HTTPException(409, 'Remove endterm room assignments before changing event type')
    for key, value in payload.model_dump().items():
        setattr(result, key, value)
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
    if assessment.event_type != 'ENDTERM':
        raise HTTPException(422, 'Room/group assignments belong to the endterm event')
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
