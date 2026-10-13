import os
from pathlib import Path
from uuid import uuid4
import pytest
from sqlalchemy import text
from sqlalchemy.schema import CreateSchema, DropSchema
from alembic import command
from alembic.config import Config
from app.database import get_engine
from test_assessments import setup, BASE
from app.document_generation.service import DocumentType

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS') != '1', reason='Requires local PostgreSQL')]

@pytest.mark.parametrize('role', ['LECTURER', 'ADMIN'])
def test_render_permissions_and_time_roundtrip(setup, role):
    client, h, cid, _, _ = setup(role)
    path = f'{BASE}/{cid}'
    endpoint = path+'/documents/ENDTERM_TEST_INFORMATION/latex'
    assert client.get(endpoint, headers=h).status_code == 422
    dates = client.get(path+'/documents/DATES_OF_ASSESSMENTS/latex', headers=h)
    assert dates.status_code == 200 and dates.headers['content-type'].startswith('text/plain')
    assert dates.headers['cache-control'] == 'no-store'
    created = client.post(path+'/events', headers=h, json={'event_type':'ENDTERM','start_time':'10:00','end_time':'12:00','writing_start_time':'10:15','writing_end_time':'11:45','latest_arrival_time':'10:05'})
    assert created.status_code == 201, created.text
    assert created.json()['writing_start_time'] == '10:15:00'
    event_path = path+'/events/'+str(created.json()['id'])
    for data in [ {'writing_start_time':'12:00','writing_end_time':'12:00'}, {'writing_start_time':'12:00','writing_end_time':'11:00'}, {'writing_start_time':'10:00Z'} ]:
        assert client.put(event_path, headers=h, json={'event_type':'ENDTERM', **data}).status_code == 422
    rendered = client.get(endpoint, headers=h)
    assert rendered.status_code == 200 and '10:15--11:45' in rendered.text
    assert '10:05' in rendered.text
    for kind in DocumentType:
        preview = client.get(path+f'/documents/{kind.value}/latex', headers=h)
        assert preview.status_code == 200, preview.text
        assert preview.headers['content-type'].startswith('text/plain')
        assert preview.headers['cache-control'] == 'no-store'
        assert preview.text.startswith(r'\documentclass')
    updated = client.put(event_path, headers=h, json={'event_type':'ENDTERM'})
    assert updated.json()['writing_start_time'] is None and updated.json()['latest_arrival_time'] is None
    assert client.get(path+'/documents/UNSUPPORTED/latex', headers=h).status_code == 422
    assert client.get(BASE+'/999999999/documents/DATES_OF_ASSESSMENTS/latex', headers=h).status_code == 404

@pytest.mark.parametrize('role', ['STUDENT','DEMONSTRATOR'])
def test_preview_denied(setup, accounts, role):
    client, _, cid, _, _ = setup()
    _, h = accounts(role)
    for kind in [item.value for item in DocumentType]:
        url = f'{BASE}/{cid}/documents/{kind}/latex'
        assert client.get(url, headers=h).status_code == 403
        assert client.get(url).status_code == 401

def test_0011_preserves_existing_schedule_and_arrival():
    schema = 'dmi_writing_' + uuid4().hex
    with get_engine().begin() as conn:
        conn.execute(CreateSchema(schema))
        try:
            conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
            config.attributes['connection'] = conn
            command.upgrade(config, '0010')
            cid = conn.scalar(text("INSERT INTO assessment_configurations(academic_year_start,term,display_label) VALUES (2026,'SPRING','Spring') RETURNING id"))
            conn.execute(text("INSERT INTO assessment_events(configuration_id,event_type,start_time,end_time,latest_arrival_time) VALUES (:cid,'ENDTERM','10:00','12:00','10:05')"), {'cid':cid})
            before = dict(conn.execute(text('SELECT * FROM assessment_events')).mappings().one())
            command.upgrade(config, '0011')
            after = dict(conn.execute(text('SELECT * FROM assessment_events')).mappings().one())
            assert after.pop('writing_start_time') is None and after.pop('writing_end_time') is None
            assert before == after
            command.downgrade(config, '0010')
            assert dict(conn.execute(text('SELECT * FROM assessment_events')).mappings().one()) == before
            command.upgrade(config, '0011')
        finally:
            conn.execute(text('SET LOCAL search_path TO public'))
            conn.execute(DropSchema(schema, cascade=True))
