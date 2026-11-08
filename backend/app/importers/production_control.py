"""Guardrails for the separately authorized production question-import runner.

The ordinary importer intentionally remains local-only. These helpers do not
connect anywhere themselves: the production runner must opt in explicitly,
prove that a non-secret backup-attestation file matches its selected target,
and then reuse the same closed-batch importer logic.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.engine import Engine


INSPECTION_ACKNOWLEDGEMENT = "AXIOM_PRODUCTION_IMPORT_INSPECTION_APPROVED"
WRITE_ACKNOWLEDGEMENT = "AXIOM_PRODUCTION_IMPORT_WRITE_APPROVED"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True)
class BackupEvidence:
    target_host: str
    database: str
    recovery_point: str
    verified_by: str


def load_backup_evidence(path: Path) -> BackupEvidence:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Backup evidence must be a readable JSON document.") from exc
    if not isinstance(data, dict) or data.get("backup_verified") is not True:
        raise RuntimeError("Backup evidence must explicitly confirm backup_verified=true.")
    values = {name: data.get(name) for name in ("target_host", "database", "recovery_point", "verified_by")}
    if any(not isinstance(value, str) or not value.strip() for value in values.values()):
        raise RuntimeError("Backup evidence is missing a required non-secret verification field.")
    return BackupEvidence(**values)


def authorize_production_import(
    engine: Engine,
    *,
    inspection_acknowledgement: str,
    backup_evidence: BackupEvidence,
    apply: bool,
    write_acknowledgement: str | None = None,
) -> None:
    """Fail closed before any production importer query or write."""
    url = engine.url
    if inspection_acknowledgement != INSPECTION_ACKNOWLEDGEMENT:
        raise RuntimeError("Production import requires the explicit inspection acknowledgement.")
    if url.get_backend_name() != "postgresql" or not url.host or url.host.lower() in LOCAL_HOSTS:
        raise RuntimeError("Production import runner refuses local or non-PostgreSQL targets.")
    if not url.database or url.database == "dmi_platform":
        raise RuntimeError("Production import runner requires an explicitly configured non-local database.")
    if backup_evidence.target_host.lower() != url.host.lower() or backup_evidence.database != url.database:
        raise RuntimeError("Backup evidence does not match the selected database target.")
    if apply and write_acknowledgement != WRITE_ACKNOWLEDGEMENT:
        raise RuntimeError("Production writes require the explicit write acknowledgement.")
