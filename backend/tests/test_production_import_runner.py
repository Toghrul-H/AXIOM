import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine

from app.importers.dmi_verified import ImportItem, ImportReport
from app.importers.production_control import (
    INSPECTION_ACKNOWLEDGEMENT,
    WRITE_ACKNOWLEDGEMENT,
    authorize_production_import,
    get_production_import_engine,
    load_backup_evidence,
    require_production_revision,
    verify_persisted_items,
)
from app.scripts.import_verified_dmi_production import MANIFEST_FIELDS, load_manifest, safe_report


def backup_file(tmp_path, **overrides):
    data = {
        "backup_verified": True,
        "target_host": "production.example.test",
        "database": "axiom_production",
        "recovery_point": "verified-recovery-point",
        "verified_by": "release-owner",
    }
    data.update(overrides)
    path = tmp_path / "backup-evidence.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def production_engine():
    return create_engine("postgresql+psycopg://runner:ignored@production.example.test/axiom_production")


def test_production_runner_requires_a_separate_import_database_url(monkeypatch):
    monkeypatch.delenv("AXIOM_PRODUCTION_IMPORT_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="AXIOM_PRODUCTION_IMPORT_DATABASE_URL"):
        get_production_import_engine()
    monkeypatch.setenv(
        "AXIOM_PRODUCTION_IMPORT_DATABASE_URL",
        "postgresql+psycopg://runner:ignored@production.example.test/axiom_production",
    )
    assert get_production_import_engine().url.host == "production.example.test"


def test_production_authorization_requires_acknowledgements_and_matching_backup(tmp_path):
    evidence = load_backup_evidence(backup_file(tmp_path))
    with pytest.raises(RuntimeError, match="inspection"):
        authorize_production_import(production_engine(), inspection_acknowledgement="no", backup_evidence=evidence, apply=False)
    with pytest.raises(RuntimeError, match="write"):
        authorize_production_import(production_engine(), inspection_acknowledgement=INSPECTION_ACKNOWLEDGEMENT, backup_evidence=evidence, apply=True)
    authorize_production_import(
        production_engine(),
        inspection_acknowledgement=INSPECTION_ACKNOWLEDGEMENT,
        backup_evidence=evidence,
        apply=True,
        write_acknowledgement=WRITE_ACKNOWLEDGEMENT,
    )


def test_production_authorization_refuses_local_target_and_bad_backup(tmp_path):
    evidence = load_backup_evidence(backup_file(tmp_path, target_host="other.example.test"))
    with pytest.raises(RuntimeError, match="Backup evidence"):
        authorize_production_import(production_engine(), inspection_acknowledgement=INSPECTION_ACKNOWLEDGEMENT, backup_evidence=evidence, apply=False)
    local = create_engine("postgresql+psycopg://runner:ignored@localhost/not_dmi_platform")
    with pytest.raises(RuntimeError, match="local"):
        authorize_production_import(local, inspection_acknowledgement=INSPECTION_ACKNOWLEDGEMENT, backup_evidence=load_backup_evidence(backup_file(tmp_path, target_host="localhost", database="not_dmi_platform")), apply=False)


def test_revision_must_be_0017():
    require_production_revision(SimpleNamespace(scalars=lambda _: ["0017"]))
    with pytest.raises(RuntimeError, match="0017"):
        require_production_revision(SimpleNamespace(scalars=lambda _: ["0016"]))


def test_manifest_is_exact_and_stays_under_its_reviewed_root(tmp_path):
    manifest = {}
    for batch, fields in MANIFEST_FIELDS.items():
        directory = tmp_path / batch
        directory.mkdir()
        values = {}
        for field, name in zip(fields, ("ready-for-m10b.json", "canonical-solutions.json", "verification-evidence.json", "grading-configurations.json") if batch == "m10a3" else ("m10c-import-ready.json", "recovered-question-master.json", "solution-verification.json") if batch == "m10c" else ("m10e-import-ready.json", "recovery-master.json", "verification-evidence.json"), strict=True):
            file = directory / name
            file.write_text("{}", encoding="utf-8")
            values[field] = str(file.relative_to(tmp_path))
        manifest[batch] = values
    path = tmp_path / "production-import-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert set(load_manifest(path)) == set(MANIFEST_FIELDS)
    manifest["m10e"]["dataset"] = "../outside.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RuntimeError, match="unexpected"):
        load_manifest(path)


def test_post_import_verification_and_report_are_sanitized():
    item = ImportItem("M10A-aaaaaaaaaaaa", "Title", "Source", "Question", "Answer", "Explanation", "sets", "easy", "DEFINITION")
    question = SimpleNamespace(
        external_source_id=item.external_source_id, source_reference=item.source_reference,
        title=item.title, difficulty=item.difficulty, response_type=item.response_type,
        skill_type=item.skill_type, question_text=item.question_text,
        expected_answer=item.expected_answer, explanation=item.explanation,
        topic=SimpleNamespace(slug=item.topic_slug),
    )
    verify_persisted_items(SimpleNamespace(scalars=lambda _: [question]), [item])
    report = ImportReport(dataset="C:/private/artifacts", dry_run=True, target="secret-host", validated=1, created=1)
    output = safe_report(dry_run=True, reports={"m10a3": report}, total=report, verified=False)
    assert "private" not in output and "secret-host" not in output and '"validated": 1' in output
