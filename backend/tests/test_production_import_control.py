import json

import pytest
from sqlalchemy import URL, create_engine

from app.importers.production_control import (
    INSPECTION_ACKNOWLEDGEMENT,
    WRITE_ACKNOWLEDGEMENT,
    authorize_production_import,
    load_backup_evidence,
)


def remote_engine():
    return create_engine(URL.create("postgresql+psycopg", host="db.example.test", database="axiom_production"))


def evidence(tmp_path, **updates):
    data = {
        "backup_verified": True,
        "target_host": "db.example.test",
        "database": "axiom_production",
        "recovery_point": "provider-restore-point-123",
        "verified_by": "authorized operator",
    }
    data.update(updates)
    path = tmp_path / "backup-evidence.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return load_backup_evidence(path)


def test_production_import_dry_run_requires_acknowledgement_and_matching_backup(tmp_path):
    backup = evidence(tmp_path)
    with pytest.raises(RuntimeError, match="acknowledgement"):
        authorize_production_import(remote_engine(), inspection_acknowledgement="no", backup_evidence=backup, apply=False)
    authorize_production_import(remote_engine(), inspection_acknowledgement=INSPECTION_ACKNOWLEDGEMENT, backup_evidence=backup, apply=False)
    with pytest.raises(RuntimeError, match="does not match"):
        authorize_production_import(remote_engine(), inspection_acknowledgement=INSPECTION_ACKNOWLEDGEMENT, backup_evidence=evidence(tmp_path, database="other"), apply=False)


def test_production_import_write_needs_second_acknowledgement_and_refuses_local_target(tmp_path):
    backup = evidence(tmp_path)
    with pytest.raises(RuntimeError, match="write acknowledgement"):
        authorize_production_import(remote_engine(), inspection_acknowledgement=INSPECTION_ACKNOWLEDGEMENT, backup_evidence=backup, apply=True)
    authorize_production_import(remote_engine(), inspection_acknowledgement=INSPECTION_ACKNOWLEDGEMENT, backup_evidence=backup, apply=True, write_acknowledgement=WRITE_ACKNOWLEDGEMENT)
    local = create_engine(URL.create("postgresql+psycopg", host="localhost", database="dmi_platform"))
    with pytest.raises(RuntimeError, match="local"):
        authorize_production_import(local, inspection_acknowledgement=INSPECTION_ACKNOWLEDGEMENT, backup_evidence=backup, apply=False)


def test_invalid_backup_evidence_is_rejected(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"backup_verified": False}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="backup_verified"):
        load_backup_evidence(path)
