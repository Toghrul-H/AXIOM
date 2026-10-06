import os
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, func, text
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema
from alembic import command
from alembic.config import Config
from app.main import app
from app.database import get_engine
from app.assessment_models import AssessmentConfiguration, AssessmentEvent, AssessmentRoom, AssessmentRoomGroup

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS') != '1', reason='Requires local PostgreSQL')]
BASE = '/assessment-configurations'

@pytest.fixture
def setup(accounts):
    created = []
    with TestClient(app) as client:
        def make(role='LECTURER'):
            user, headers = accounts(role)
            with Session(get_engine()) as session:
                used = set(session.scalars(select(AssessmentConfiguration.academic_year_start)))
            year = next(y for y in range(8000, 9999) if y not in used)
            response = client.post(BASE, headers=headers, json={'academic_year_start': year, 'term': 'FALL', 'display_label': 'Test semester'})
            assert response.status_code == 201, response.text
            cid = response.json()['id']; created.append(cid)
            return client, headers, cid, year, user
        yield make
    with Session(get_engine()) as session:
        session.execute(delete(AssessmentConfiguration).where(AssessmentConfiguration.id.in_(created)))
        session.commit()

@pytest.mark.parametrize('role', ['LECTURER', 'ADMIN'])
def test_configuration_crud_and_uniqueness(setup, role):
    client, h, cid, year, user = setup(role)
    path = f'{BASE}/{cid}'
    assert client.get(BASE, headers=h).status_code == 200
    assert client.get(path, headers=h).json()['events'] == []
    assert client.post(BASE, headers=h, json={'academic_year_start': year, 'term': 'FALL', 'display_label': 'duplicate'}).status_code == 409
    changed = client.patch(path, headers=h, json={'display_label': '  Updated  '})
    assert changed.status_code == 200 and changed.json()['display_label'] == 'Updated'
    assert changed.json()['last_modified_by_id'] == user['id']
    assert client.patch(path, headers=h, json={'display_label': None}).status_code == 422
    assert client.delete(path, headers=h).status_code == 204
    assert client.get(path, headers=h).status_code == 404

@pytest.mark.parametrize('role', ['STUDENT', 'DEMONSTRATOR'])
def test_denied_all_management(setup, accounts, role):
    client, _, cid, _, _ = setup()
    _, h = accounts(role)
    path = f'{BASE}/{cid}'
    for method, url in [('GET', BASE), ('GET', path), ('POST', BASE), ('PATCH', path), ('DELETE', path),
        ('POST', path+'/events'), ('PUT', path+'/events/1'), ('DELETE', path+'/events/1'),
        ('POST', path+'/events/1/rooms'), ('PUT', path+'/events/1/rooms/1'), ('DELETE', path+'/events/1/rooms/1')]:
        assert client.request(method, url, headers=h, json={} if method in {'POST', 'PUT', 'PATCH'} else None).status_code == 403

def test_events_rooms_validation_and_cascade(setup):
    client, h, cid, _, _ = setup()
    path = f'{BASE}/{cid}'
    created = client.post(path+'/events', headers=h, json={'event_type': 'ENDTERM', 'date': '2027-05-19', 'start_time': '10:00', 'end_time': '12:00', 'latest_arrival_time': '09:45', 'document_date': '2027-05-01'})
    assert created.status_code == 201, created.text
    eid = created.json()['id']; ep = f'{path}/events/{eid}'
    assert created.json()['date'] == '2027-05-19'
    for payload in [ {'event_type': 'ENDTERM', 'start_time': '12:00', 'end_time': '12:00'},
        {'event_type': 'ENDTERM', 'start_time': '12:00', 'end_time': '11:00'},
        {'event_type': 'ENDTERM', 'start_time': '12:00Z'}, {'event_type': 'ENDTERM', 'venue': ' '} ]:
        assert client.put(ep, headers=h, json=payload).status_code == 422
    assert client.put(ep, headers=h, json={'event_type': 'ENDTERM', 'notes': 'Details pending'}).status_code == 200
    assert client.post(path+'/events', headers=h, json={'event_type': 'ENDTERM'}).status_code == 409
    rp = ep+'/rooms'
    for groups in [[], ['1', '1'], ['1', ' 1 ']]:
        assert client.post(rp, headers=h, json={'room': 'R1', 'groups': groups}).status_code == 422
    assert client.post(rp, headers=h, json={'room': ' ', 'groups': ['1']}).status_code == 422
    first = client.post(rp, headers=h, json={'room': ' R1 ', 'groups': ['1', '42', 'lab-A']})
    assert first.status_code == 201, first.text
    rid = first.json()['id']
    assert client.post(rp, headers=h, json={'room': 'R2', 'groups': ['42']}).status_code == 409
    second = client.post(rp, headers=h, json={'room': 'R2', 'groups': ['100']})
    assert second.status_code == 201
    assert client.put(rp+f'/{rid}', headers=h, json={'room': 'Changed', 'groups': ['1', '9']}).status_code == 200
    assert client.put(rp+f'/{rid}', headers=h, json={'room': 'Changed', 'groups': ['100']}).status_code == 409
    detail = client.get(path, headers=h).json()
    assert len(detail['events'][0]['rooms']) == 2
    assert client.put(ep, headers=h, json={'event_type': 'COURSEWORK_PUBLICATION'}).status_code == 409
    assert client.delete(rp+f'/{rid}', headers=h).status_code == 204
    assert client.delete(ep, headers=h).status_code == 204
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count()).select_from(AssessmentRoom).where(AssessmentRoom.event_id == eid)) == 0
        assert session.scalar(select(func.count()).select_from(AssessmentRoomGroup).where(AssessmentRoomGroup.event_id == eid)) == 0
    # Configuration deletion also cascades through an entire populated graph.
    eid = client.post(path+'/events', headers=h, json={'event_type': 'ENDTERM'}).json()['id']
    assert client.post(f'{path}/events/{eid}/rooms', headers=h, json={'room': 'Room', 'groups': ['X']}).status_code == 201
    assert client.delete(path, headers=h).status_code == 204
    with Session(get_engine()) as session:
        assert session.get(AssessmentEvent, eid) is None
        assert session.scalar(select(func.count()).select_from(AssessmentRoomGroup).where(AssessmentRoomGroup.event_id == eid)) == 0

def test_parent_scoping_optional_schedule_and_metadata_validation(setup):
    client, h, cid, _, _ = setup()
    _, _, other, _, _ = setup()
    path = f'{BASE}/{cid}'
    event = client.post(path+'/events', headers=h, json={'event_type': 'COURSEWORK_PUBLICATION', 'notes': 'During the final teaching week'})
    assert event.status_code == 201 and event.json()['date'] is None
    eid = event.json()['id']
    assert client.delete(f'{BASE}/{other}/events/{eid}', headers=h).status_code == 404
    assert client.post(f'{path}/events/{eid}/rooms', headers=h, json={'room': 'R', 'groups': ['1']}).status_code == 422
    for payload in [{'term': 'WINTER'}, {'academic_year_start': 0}, {'display_label': ' '}]:
        assert client.patch(path, headers=h, json=payload).status_code == 422
    assert client.get(path).status_code == 401

def test_0010_roundtrip_only_adds_owned_tables():
    schema = 'dmi_assessment_' + uuid4().hex
    with get_engine().begin() as conn:
        conn.execute(CreateSchema(schema))
        try:
            conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
            config.attributes['connection'] = conn
            command.upgrade(config, '0009')
            before = list(conn.execute(text('SELECT * FROM users ORDER BY id')).mappings())
            command.upgrade(config, '0010')
            assert list(conn.execute(text('SELECT * FROM users ORDER BY id')).mappings()) == before
            conn.execute(text("INSERT INTO assessment_configurations(academic_year_start,term,display_label) VALUES (2026,'FALL','Fall')"))
            command.downgrade(config, '0009')
            assert list(conn.execute(text('SELECT * FROM users ORDER BY id')).mappings()) == before
            command.upgrade(config, '0010')
        finally:
            conn.execute(text('SET LOCAL search_path TO public'))
            conn.execute(DropSchema(schema, cascade=True))

def test_rooms_are_scoped_to_each_applicable_event(setup):
    client, h, cid, _, _ = setup()
    path = f'{BASE}/{cid}'
    event_ids = []
    for kind in ['MIDTERM', 'ENDTERM', 'SHORT_QUIZ_RETAKE', 'TEST_RETAKE']:
        response = client.post(path+'/events', headers=h, json={'event_type': kind})
        assert response.status_code == 201
        value = response.json()
        assert value['venue'] is None and value['rooms'] == []
        eid = value['id']; event_ids.append(eid)
        rooms = f'{path}/events/{eid}/rooms'
        assert client.post(rooms, headers=h, json={'room': kind+' room', 'groups': ['lab-A']}).status_code == 201
        assert client.post(rooms, headers=h, json={'room': 'Other room', 'groups': ['lab-A']}).status_code == 409
    # Moving among supported types keeps existing assignments.
    assert client.delete(f'{path}/events/{event_ids[1]}', headers=h).status_code == 204
    moved = client.put(f'{path}/events/{event_ids[0]}', headers=h, json={'event_type': 'ENDTERM'})
    assert moved.status_code == 200 and len(moved.json()['rooms']) == 1
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count()).select_from(AssessmentRoomGroup).where(AssessmentRoomGroup.event_id == event_ids[1])) == 0
    assert client.delete(path, headers=h).status_code == 204
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count()).select_from(AssessmentRoomGroup).where(AssessmentRoomGroup.event_id.in_(event_ids))) == 0
