"""Regression coverage for JSON server defaults in historical migrations."""

import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateColumn


ROOT = Path(__file__).resolve().parents[1]


def load_migration(revision: str):
    path = next((ROOT / "alembic" / "versions").glob(f"{revision}_*.py"))
    spec = importlib.util.spec_from_file_location(f"migration_{revision}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("revision", "table_name", "expected_institution"),
    [
        ("0020", "practice_sheets", "Eötvös Loránd University"),
        ("0021", "exams", "Eötvös Loránd University"),
    ],
)
def test_document_settings_defaults_compile_as_bound_safe_postgresql_literals(monkeypatch, revision, table_name, expected_institution):
    migration = load_migration(revision)
    defaults = json.loads(migration._DEFAULT_SETTINGS)
    assert defaults["header"]["institution_name"] == expected_institution

    captured = []
    monkeypatch.setattr(migration.op, "add_column", lambda table, column: captured.append((table, column)))
    migration.upgrade()
    assert captured and captured[0][0] == table_name
    column = captured[0][1]
    # ``sa.text`` would expose JSON values such as ``:null`` as bind names.
    # A literal BindParameter renders the complete JSON as one SQL string.
    assert not hasattr(column.server_default.arg, "_bindparams")
    sql = str(CreateColumn(column).compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "DEFAULT" in sql
    assert expected_institution in sql
    assert ":null" in sql and ":true" in sql
