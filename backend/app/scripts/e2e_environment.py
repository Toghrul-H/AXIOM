"""Create or remove a schema-isolated, local-only browser E2E environment.

This command never uses a production target. It creates application tables in
one explicitly named schema within local ``dmi_platform`` and drops only that
same schema during cleanup. The caller must provide a non-production password
through ``AXIOM_E2E_PASSWORD``; it is neither printed nor stored in source.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.auth import passwords
from app.auth_models import User
from app.config import get_settings
from app.database import get_engine
from app.importers.dmi_verified import assert_local_development_engine
from app.models import Question, Topic

PREFIX = "axiom_e2e_"
STUDENT_EMAIL = "e2e.student@example.com"
LECTURER_EMAIL = "e2e.lecturer@example.com"


def _require_schema(schema: str) -> None:
    if not schema.startswith(PREFIX) or len(schema) <= len(PREFIX):
        raise RuntimeError(f"Refusing E2E operation: schema must start with {PREFIX!r}.")


def _raw_engine():
    settings = get_settings()
    engine = create_engine(settings.database_url(), pool_pre_ping=True, hide_parameters=True)
    assert_local_development_engine(engine)
    return engine


def _migrate() -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    command.upgrade(config, "head")


def create(schema: str, password: str) -> None:
    _require_schema(schema)
    if not 12 <= len(password) <= 128:
        raise RuntimeError("AXIOM_E2E_PASSWORD must be 12–128 characters.")
    raw = _raw_engine()
    with raw.begin() as connection:
        if connection.scalar(text("SELECT 1 FROM pg_namespace WHERE nspname=:schema"), {"schema": schema}):
            raise RuntimeError(f"Refusing to reuse existing E2E schema {schema!r}.")
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        _migrate()
        with Session(get_engine()) as session, session.begin():
            logic = session.scalar(select(Topic).where(Topic.slug == "logic"))
            if logic is None:
                raise RuntimeError("Seeded logic topic is missing after migration.")
            digest = passwords.hash(password)
            session.add_all((
                User(email=STUDENT_EMAIL, password_hash=digest, role="STUDENT", email_verified=True),
                User(email=LECTURER_EMAIL, password_hash=digest, role="LECTURER", email_verified=True),
            ))
            for number in range(1, 4):
                session.add(Question(
                    # Retain the curated namespace required by the practice
                    # selector while making fixture provenance unique to this
                    # disposable schema.
                    external_source_id=f"M10A3:E2E-{schema}-{number}",
                    source_reference="M12A isolated E2E fixture",
                    topic=logic,
                    title=f"E2E Logic Practice {number}",
                    difficulty="easy",
                    response_type="FREE_RESPONSE",
                    skill_type="PROOF",
                    question_text=f"Give a short proof for E2E fixture {number}.",
                    expected_answer=f"Reference proof {number}.",
                    correct_boolean=None,
                    explanation=f"Worked E2E explanation {number}.",
                    is_active=True,
                ))
        print(f"Created isolated E2E schema {schema}; seeded {STUDENT_EMAIL} and {LECTURER_EMAIL}.")
    except Exception:
        destroy(schema)
        raise


def destroy(schema: str) -> None:
    _require_schema(schema)
    raw = _raw_engine()
    with raw.begin() as connection:
        connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    print(f"Removed isolated E2E schema {schema}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "destroy"))
    parser.add_argument("--schema", required=True, help=f"Temporary schema beginning with {PREFIX}")
    args = parser.parse_args()
    os.environ["DATABASE_SCHEMA"] = args.schema
    get_settings.cache_clear()
    get_engine.cache_clear()
    if args.action == "destroy":
        destroy(args.schema)
        return
    password = os.environ.get("AXIOM_E2E_PASSWORD", "")
    create(args.schema, password)


if __name__ == "__main__":
    main()
