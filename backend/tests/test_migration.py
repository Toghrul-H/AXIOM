import json
import os
from pathlib import Path
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.schema import CreateSchema, DropSchema
from app.database import get_engine

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Set RUN_POSTGRES_TESTS=1")]


def test_legacy_migration_preserves_data():
    # This schema belongs only to this test; public course tables are untouched.
    schema = f"dmi_migration_test_{uuid4().hex}"
    with get_engine().begin() as connection:
        connection.execute(CreateSchema(schema))
        try:
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "0001")
            rows = [
                (101, "Relations", "short_answer", "Reference proof", None),
                (102, "Graph Theory", "true_false", "false", None),
                (103, "Custom historical topic", "multiple_choice", "A", ["A", "B"]),
            ]
            for question_id, topic, kind, answer, options in rows:
                connection.execute(text("""INSERT INTO questions(id,topic,difficulty,question_type,question_text,correct_answer,explanation,options,created_at)
                    VALUES (:id,:topic,'medium',:kind,'Original text',:answer,'Original explanation',CAST(:options AS jsonb),'2026-09-01T12:00:00Z')"""),
                    {"id": question_id, "topic": topic, "kind": kind, "answer": answer, "options": json.dumps(options) if options else None})
            command.upgrade(config, "head")
            migrated = connection.execute(text("SELECT q.*, t.name AS topic_name FROM questions q JOIN topics t ON t.id=q.topic_id ORDER BY q.id")).mappings().all()
            assert len(migrated) == 3
            assert [r["id"] for r in migrated] == [101, 102, 103]
            assert [r["topic_name"] for r in migrated] == ["Binary Relations", "Graphs", "Custom historical topic"]
            assert migrated[0]["expected_answer"] == "Reference proof"
            assert migrated[1]["correct_boolean"] is False
            assert migrated[2]["response_type"] == "SINGLE_CHOICE"
            assert all(r["question_text"] == "Original text" and r["explanation"] == "Original explanation" and r["skill_type"] == "UNSPECIFIED" and r["created_at"] == r["updated_at"] for r in migrated)
            options = connection.execute(text("SELECT text,is_correct,position FROM question_options WHERE question_id=103 ORDER BY position")).all()
            assert options == [("A", True, 0), ("B", False, 1)]
        finally:
            connection.execute(text("SET LOCAL search_path TO public"))
            connection.execute(DropSchema(schema, cascade=True))


@pytest.mark.parametrize('submitted', [False, True])
def test_0005_preserves_attempt_snapshots_and_bootstraps_admin(submitted, monkeypatch, capsys):
    from sqlalchemy.orm import Session
    from app.auth import passwords
    from app.auth_models import User
    from app.scripts import create_admin
    from conftest import TEST_PASSWORD
    schema = f'dmi_auth_migration_{uuid4().hex}'
    with get_engine().begin() as connection:
        connection.execute(CreateSchema(schema))
        try:
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
            config.attributes['connection'] = connection
            command.upgrade(config, '0004')
            connection.execute(text("INSERT INTO quizzes(id,title,status) VALUES (1,'Preserved quiz','ACTIVE')"))
            attempt, identity = uuid4(), uuid4()
            connection.execute(text("""INSERT INTO quiz_attempts
                (id,quiz_id,development_session_id,quiz_title,status,objective_total,objective_score,submitted_at)
                VALUES (:id,1,:identity,'Historical title',:status,2,:score,:submitted)"""),
                {'id':attempt,'identity':identity,'status':'SUBMITTED' if submitted else 'IN_PROGRESS',
                 'score':2 if submitted else None,'submitted':'2026-09-01T12:00:00Z' if submitted else None})
            connection.execute(text("""INSERT INTO attempt_answers
                (id,quiz_attempt_id,position,points,question_text,response_type,expected_answer,explanation,free_response,topic_slug)
                VALUES (1,:id,0,2,'Original snapshot','FREE_RESPONSE','Reference ∀x','Original explanation','Saved ∩ answer','sets')"""),{'id':attempt})
            connection.execute(text("INSERT INTO attempt_options(id,attempt_answer_id,text,is_correct,position) VALUES (1,1,'Historical option',true,0)"))
            before = {table:connection.execute(text(f'SELECT * FROM {table}')).mappings().all()
                      for table in ['quizzes','quiz_attempts','attempt_answers','attempt_options']}
            command.upgrade(config, 'head')
            for table, rows in before.items():
                after=connection.execute(text(f'SELECT * FROM {table}')).mappings().all()
                assert [{k:row[k] for k in rows[0]} for row in after] == [dict(row) for row in rows]
            legacy=connection.execute(text('SELECT * FROM users WHERE is_legacy=true')).mappings().one()
            assert not legacy['is_active'] and legacy['password_hash'] is None
            assert connection.scalar(text('SELECT user_id FROM quiz_attempts'))==legacy['id']
            assert connection.scalar(text("SELECT is_nullable FROM information_schema.columns WHERE table_schema=:schema AND table_name='quiz_attempts' AND column_name='user_id'"),{'schema':schema})=='NO'
            assert connection.scalar(text("SELECT is_nullable FROM information_schema.columns WHERE table_schema=:schema AND table_name='quiz_attempts' AND column_name='development_session_id'"),{'schema':schema})=='YES'
            # Execute the actual interactive command with test-only input. No real credentials.
            monkeypatch.setattr(create_admin,'get_engine',lambda:connection)
            monkeypatch.setattr(create_admin,'Session',lambda bind:Session(bind,join_transaction_mode='create_savepoint'))
            monkeypatch.setattr('builtins.input',lambda prompt:'  Bootstrap@Example.com  ')
            monkeypatch.setattr(create_admin,'getpass',lambda prompt:TEST_PASSWORD)
            create_admin.main()
            output=capsys.readouterr().out
            assert 'Administrator created' in output and TEST_PASSWORD not in output
            with Session(connection,join_transaction_mode='create_savepoint') as session:
                admin=session.query(User).filter_by(role='ADMIN').one()
                assert admin.email=='bootstrap@example.com' and admin.is_active
                assert passwords.verify(TEST_PASSWORD,admin.password_hash)
            with pytest.raises(SystemExit,match='already exists'):
                create_admin.main()
        finally:
            connection.execute(text('SET LOCAL search_path TO public'))
            connection.execute(DropSchema(schema,cascade=True))
