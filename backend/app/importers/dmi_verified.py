"""Validated, atomic import support for explicitly reviewed DMI batches.

This module deliberately has no route or startup hook.  The CLI is the only
entry point for importing an external, reviewed dataset.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re
from typing import Any, Callable, Iterable

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.models import Question, ResponseType, SkillType, Topic


EXTERNAL_NAMESPACE = "M10A3:"
CANONICAL_ID = re.compile(r"^M10A-[0-9a-f]{12}$")

# These are the only M10A.3 records reviewed for this import batch.  Keeping
# the allow-list in code prevents a hand-edited ready JSON from importing one
# of the 102 explicitly blocked records.
READY_IDS = frozenset({
    "M10A-da76c4d2f484", "M10A-37bb12da70a2", "M10A-ea4716f1d117",
    "M10A-39170e771614", "M10A-4ac31012f1a2", "M10A-43dbe7dbeaf4",
    "M10A-048cb14f9e8c", "M10A-896b66c5c7d1", "M10A-34bc1776243b",
    "M10A-220051b32d66", "M10A-3a4398205aed", "M10A-8eb59167c944",
    "M10A-5f24fbcb9ec6", "M10A-c50775f7b580", "M10A-fe9b615137d2",
    "M10A-cc9b06e75b1b", "M10A-241631d77fb1", "M10A-d37c938ddd29",
    "M10A-b9cea942c076", "M10A-1b1d5d0d9f5b", "M10A-59dd439ae88f",
    "M10A-9991c3f0250c", "M10A-07ae62ed1f9d",
})

# Required schema fields absent from the analysis artifact are explicitly
# curated here, by canonical ID. These classifications are not inferred from
# the question text at import time.
IMPORT_METADATA: dict[str, tuple[str, str, str]] = {
    "M10A-da76c4d2f484": ("sets", "hard", "PROOF"),
    "M10A-37bb12da70a2": ("binary-relations", "hard", "CALCULATION"),
    "M10A-ea4716f1d117": ("sets", "hard", "PROOF"),
    "M10A-39170e771614": ("sets", "hard", "PROOF"),
    "M10A-4ac31012f1a2": ("sets", "hard", "PROOF"),
    "M10A-43dbe7dbeaf4": ("sets", "medium", "PROOF"),
    "M10A-048cb14f9e8c": ("sets", "hard", "PROOF"),
    "M10A-896b66c5c7d1": ("binary-relations", "easy", "DEFINITION"),
    "M10A-34bc1776243b": ("combinatorics", "medium", "THEOREM"),
    "M10A-220051b32d66": ("combinatorics", "easy", "THEOREM"),
    "M10A-3a4398205aed": ("combinatorics", "easy", "THEOREM"),
    "M10A-8eb59167c944": ("logic", "easy", "APPLICATION"),
    "M10A-5f24fbcb9ec6": ("logic", "medium", "APPLICATION"),
    "M10A-c50775f7b580": ("sets", "easy", "CALCULATION"),
    "M10A-fe9b615137d2": ("sets", "easy", "DEFINITION"),
    "M10A-cc9b06e75b1b": ("sets", "easy", "CALCULATION"),
    "M10A-241631d77fb1": ("binary-relations", "easy", "CALCULATION"),
    "M10A-d37c938ddd29": ("binary-relations", "easy", "DEFINITION"),
    "M10A-b9cea942c076": ("binary-relations", "easy", "CALCULATION"),
    "M10A-1b1d5d0d9f5b": ("binary-relations", "easy", "CALCULATION"),
    "M10A-59dd439ae88f": ("binary-relations", "medium", "CALCULATION"),
    "M10A-9991c3f0250c": ("binary-relations", "medium", "PROOF"),
    "M10A-07ae62ed1f9d": ("binary-relations", "medium", "CALCULATION"),
}

M10C_IDS = frozenset({
    "M10A-76335ef0a375", "M10A-89011c1f9e9e", "M10A-efe0d2ab9c42",
    "M10A-11d3c55b46c1", "M10A-863760d87ae5", "M10A-b4d38cb8329a",
    "M10A-bde9ac0520cc", "M10A-7aafd52c6d82", "M10A-e985b4c645fc",
    "M10A-419d232d2121", "M10A-57460f790ec2", "M10A-90a264b4e583",
    "M10A-a3ea409068d5", "M10A-ddf8054f0cc3",
})

# These classifications are a reviewed part of the batch definition, never
# inferred from a submitted JSON document at import time.
M10C_METADATA: dict[str, tuple[str, str, str]] = {
    "M10A-76335ef0a375": ("binary-relations", "hard", "APPLICATION"),
    "M10A-89011c1f9e9e": ("binary-relations", "hard", "CLASSIFICATION"),
    "M10A-efe0d2ab9c42": ("complex-numbers", "hard", "CALCULATION"),
    "M10A-11d3c55b46c1": ("combinatorics", "hard", "CALCULATION"),
    "M10A-863760d87ae5": ("combinatorics", "medium", "CALCULATION"),
    "M10A-b4d38cb8329a": ("combinatorics", "medium", "CALCULATION"),
    "M10A-bde9ac0520cc": ("combinatorics", "medium", "CALCULATION"),
    "M10A-7aafd52c6d82": ("combinatorics", "hard", "CALCULATION"),
    "M10A-e985b4c645fc": ("combinatorics", "hard", "CALCULATION"),
    "M10A-419d232d2121": ("combinatorics", "hard", "CALCULATION"),
    "M10A-57460f790ec2": ("combinatorics", "medium", "CALCULATION"),
    "M10A-90a264b4e583": ("combinatorics", "medium", "CALCULATION"),
    "M10A-a3ea409068d5": ("combinatorics", "medium", "CALCULATION"),
    "M10A-ddf8054f0cc3": ("combinatorics", "hard", "CALCULATION"),
}

# M10E is a separately recovered, source-verified third batch.  Its metadata
# is deliberately curated here and cross-checked against the staged artifact;
# it is never inferred from question text at import time.
M10E_IDS = frozenset({
    "M10A-027ddeca864c", "M10A-1299960f0641", "M10A-41226d6b76f4",
    "M10A-59634a8028a4", "M10A-69c2965640f4", "M10A-863178bd0a6f",
    "M10A-91cda3de8054", "M10A-a78b6eed175c", "M10A-a95e1d747f97",
    "M10A-c60d4b11aa76", "M10A-d42cf810ae16", "M10A-da6797ff4fc7",
    "M10A-e1293b8f5ba0", "M10A-f2d2989d0573", "M10A-f3bd3ad9a733",
})

M10E_METADATA: dict[str, tuple[str, str, str]] = {
    "M10A-027ddeca864c": ("binary-relations", "medium", "CLASSIFICATION"),
    "M10A-1299960f0641": ("complex-numbers", "easy", "DEFINITION"),
    "M10A-41226d6b76f4": ("binary-relations", "easy", "DEFINITION"),
    "M10A-59634a8028a4": ("sets", "easy", "DEFINITION"),
    "M10A-69c2965640f4": ("binary-relations", "medium", "CLASSIFICATION"),
    "M10A-863178bd0a6f": ("binary-relations", "medium", "CLASSIFICATION"),
    "M10A-91cda3de8054": ("binary-relations", "easy", "DEFINITION"),
    "M10A-a78b6eed175c": ("binary-relations", "medium", "CLASSIFICATION"),
    "M10A-a95e1d747f97": ("binary-relations", "medium", "CLASSIFICATION"),
    "M10A-c60d4b11aa76": ("binary-relations", "medium", "CLASSIFICATION"),
    "M10A-d42cf810ae16": ("binary-relations", "medium", "CLASSIFICATION"),
    "M10A-da6797ff4fc7": ("binary-relations", "medium", "CLASSIFICATION"),
    "M10A-e1293b8f5ba0": ("functions", "medium", "CLASSIFICATION"),
    "M10A-f2d2989d0573": ("combinatorics", "easy", "THEOREM"),
    "M10A-f3bd3ad9a733": ("functions", "easy", "DEFINITION"),
}


@dataclass(frozen=True)
class BatchSpec:
    identifier: str
    allowed_ids: frozenset[str]
    expected_count: int
    metadata: dict[str, tuple[str, str, str]]
    required_artifacts: tuple[str, ...]


BATCHES: dict[str, BatchSpec] = {
    "m10a3": BatchSpec(
        "m10a3", READY_IDS, 23, IMPORT_METADATA,
        ("ready-for-m10b.json", "canonical-solutions.json", "verification-evidence.json", "grading-configurations.json"),
    ),
    "m10c": BatchSpec(
        "m10c", M10C_IDS, 14, M10C_METADATA,
        ("m10c-import-ready.json", "recovered-question-master.json", "solution-verification.json"),
    ),
    "m10e": BatchSpec(
        "m10e", M10E_IDS, 15, M10E_METADATA,
        ("m10e-import-ready.json", "recovery-master.json", "verification-evidence.json"),
    ),
}


class DatasetValidationError(ValueError):
    """Raised before any database write for malformed/ineligible data."""


class ImportConflictError(ValueError):
    """Raised when an external ID points at different persisted content."""


@dataclass(frozen=True)
class ImportItem:
    canonical_id: str
    title: str
    source_reference: str
    question_text: str
    expected_answer: str
    explanation: str
    topic_slug: str
    difficulty: str
    skill_type: str
    response_type: str = "FREE_RESPONSE"

    @property
    def external_source_id(self) -> str:
        return f"{EXTERNAL_NAMESPACE}{self.canonical_id}"


@dataclass
class ImportReport:
    dataset: str
    dry_run: bool
    target: str
    validated: int = 0
    created: int = 0
    skipped: int = 0
    conflicts: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    topic_distribution: dict[str, int] = field(default_factory=dict)

    def json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DatasetValidationError(f"Required dataset file is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DatasetValidationError(f"Invalid JSON in {path}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise DatasetValidationError(f"Expected JSON object in {path}")
    return data


def _index(records: Any, key: str, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(records, list):
        raise DatasetValidationError(f"{label} records must be a list")
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get(key), str):
            raise DatasetValidationError(f"{label} contains an item without {key}")
        value = record[key]
        if value in indexed:
            raise DatasetValidationError(f"{label} duplicates {key}: {value}")
        indexed[value] = record
    return indexed


def _text(record: dict[str, Any], key: str, question_id: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DatasetValidationError(f"{question_id}: missing {key}")
    return value.strip()


def load_verified_dataset(
    dataset_path: Path,
    canonical_path: Path | None = None,
    evidence_path: Path | None = None,
    grading_path: Path | None = None,
    expected_ids: frozenset[str] = READY_IDS,
    metadata: dict[str, tuple[str, str, str]] | None = None,
    expected_count: int = 23,
) -> list[ImportItem]:
    """Cross-validate all M10A.3 sources before returning importable records."""
    dataset_path = dataset_path.resolve()
    root = dataset_path.parent
    ready = _read_json(dataset_path)
    canonical = _read_json(canonical_path or root / "canonical-solutions.json")
    evidence = _read_json(evidence_path or root / "verification-evidence.json")
    grading = _read_json(grading_path or root / "grading-configurations.json")
    candidates = ready.get("items")
    if not isinstance(candidates, list) or ready.get("candidate_count") != len(candidates):
        raise DatasetValidationError("ready-for-m10b candidate_count/items are inconsistent")
    ready_by_id = _index(candidates, "stable_question_id", "ready-for-m10b")
    if frozenset(ready_by_id) != expected_ids:
        raise DatasetValidationError("ready-for-m10b canonical IDs do not exactly match the approved M10A.3 allow-list")
    if len(ready_by_id) != expected_count:
        raise DatasetValidationError(f"M10A.3 import batch must contain exactly {expected_count} candidates")
    canonical_by_id = _index(canonical.get("records"), "stable_question_id", "canonical-solutions")
    evidence_by_id = _index(evidence.get("records"), "stable_question_id", "verification-evidence")
    grading_by_id = _index(grading.get("records"), "stable_question_id", "grading-configurations")
    metadata = metadata or IMPORT_METADATA
    if set(metadata) != expected_ids:
        raise RuntimeError("Importer metadata does not cover the approved allow-list")

    imported: list[ImportItem] = []
    for question_id, ready_record in ready_by_id.items():
        if not CANONICAL_ID.fullmatch(question_id):
            raise DatasetValidationError(f"Invalid canonical ID: {question_id}")
        canonical_record = canonical_by_id.get(question_id)
        evidence_record = evidence_by_id.get(question_id)
        grading_record = grading_by_id.get(question_id)
        if canonical_record is None or evidence_record is None or grading_record is None:
            raise DatasetValidationError(f"{question_id}: missing cross-reference record")
        if canonical_record.get("solution_status") != "verified_derived_solution" or evidence_record.get("solution_status") != "verified_derived_solution":
            raise DatasetValidationError(f"{question_id}: solution verification is insufficient")
        if grading_record.get("response_type") != "FREE_RESPONSE" or not grading_record.get("schema_compatible") or not grading_record.get("import_eligible"):
            raise DatasetValidationError(f"{question_id}: not an eligible FREE_RESPONSE/manual-grading record")
        source_reference = _text(ready_record, "source_reference", question_id)
        if source_reference != _text(canonical_record, "source_reference", question_id):
            raise DatasetValidationError(f"{question_id}: source provenance differs between M10A.3 files")
        question_text = _text(ready_record, "question_text", question_id)
        answer = _text(ready_record, "expected_answer", question_id)
        explanation = _text(ready_record, "explanation", question_id)
        if answer != _text(canonical_record, "final_answer", question_id) or explanation != _text(canonical_record, "worked_solution", question_id):
            raise DatasetValidationError(f"{question_id}: answer or worked solution differs between M10A.3 files")
        if _text(evidence_record, "evidence", question_id) == "":  # defensive/documentary
            raise DatasetValidationError(f"{question_id}: missing verification evidence")
        if ready_record.get("response_type") != "FREE_RESPONSE":
            raise DatasetValidationError(f"{question_id}: unsupported response type")
        topic_slug, difficulty, skill_type = metadata[question_id]
        imported.append(ImportItem(
            canonical_id=question_id, title=_text(ready_record, "title", question_id),
            source_reference=source_reference, question_text=question_text,
            expected_answer=answer, explanation=explanation, topic_slug=topic_slug,
            difficulty=difficulty, skill_type=skill_type,
        ))
    return sorted(imported, key=lambda item: item.canonical_id)


TOPIC_NAMES = {
    "Binary Relations": "binary-relations",
    "Complex Numbers": "complex-numbers",
    "Combinatorics": "combinatorics",
    "Functions": "functions",
    "Sets": "sets",
}


def load_m10c_dataset(
    dataset_path: Path,
    master_path: Path | None = None,
    verification_path: Path | None = None,
    *,
    expected_ids: frozenset[str] = M10C_IDS,
    metadata: dict[str, tuple[str, str, str]] | None = None,
    expected_count: int = 14,
) -> list[ImportItem]:
    """Validate the M10C recovery/evidence adapter before any database access."""
    dataset_path = dataset_path.resolve()
    root = dataset_path.parent
    ready = _read_json(dataset_path)
    master = _read_json(master_path or root / "recovered-question-master.json")
    verification = _read_json(verification_path or root / "solution-verification.json")
    candidates = ready.get("items")
    if not isinstance(candidates, list) or ready.get("candidate_count") != len(candidates):
        raise DatasetValidationError("m10c-import-ready candidate_count/items are inconsistent")
    ready_by_id = _index(candidates, "stable_question_id", "m10c-import-ready")
    if frozenset(ready_by_id) != expected_ids or len(ready_by_id) != expected_count:
        raise DatasetValidationError("M10C canonical IDs do not exactly match the approved batch allow-list")
    if master.get("record_count") != len(master.get("records", [])):
        raise DatasetValidationError("M10C recovered-question-master record_count/records are inconsistent")
    master_by_id = _index(master.get("records"), "stable_question_id", "recovered-question-master")
    verification_by_id = _index(verification.get("records"), "stable_question_id", "solution-verification")
    metadata = metadata or M10C_METADATA
    if set(metadata) != expected_ids:
        raise RuntimeError("M10C importer metadata does not cover the approved allow-list")

    imported: list[ImportItem] = []
    for question_id, ready_record in ready_by_id.items():
        if not CANONICAL_ID.fullmatch(question_id):
            raise DatasetValidationError(f"Invalid canonical ID: {question_id}")
        master_record = master_by_id.get(question_id)
        evidence_record = verification_by_id.get(question_id)
        if master_record is None or evidence_record is None:
            raise DatasetValidationError(f"{question_id}: missing M10C master/evidence record")
        if master_record.get("solution_status") != "verified_derived_solution" or evidence_record.get("solution_status") != "verified_derived_solution":
            raise DatasetValidationError(f"{question_id}: solution verification is insufficient")
        if master_record.get("remaining_uncertainties") is not None:
            raise DatasetValidationError(f"{question_id}: unresolved critical source uncertainty")
        source_path = _text(master_record, "original_source_path", question_id)
        page = master_record.get("source_page")
        source_evidence = _text(master_record, "source_page_evidence", question_id)
        if not isinstance(page, int) or page < 1 or not (root / source_evidence).is_file():
            raise DatasetValidationError(f"{question_id}: source-page evidence is missing")
        if not _text(evidence_record, "method", question_id) or not _text(evidence_record, "evidence", question_id):
            raise DatasetValidationError(f"{question_id}: independent verification evidence is missing")
        if not isinstance(evidence_record.get("computed"), dict) or not evidence_record["computed"]:
            raise DatasetValidationError(f"{question_id}: independent computed verification is missing")
        source_reference = _text(ready_record, "source_reference", question_id)
        if source_reference != _text(master_record, "source_reference", question_id):
            raise DatasetValidationError(f"{question_id}: source provenance differs between M10C artifacts")
        if _text(ready_record, "external_source_id", question_id) != f"{EXTERNAL_NAMESPACE}{question_id}":
            raise DatasetValidationError(f"{question_id}: external source identifier is invalid")
        question_text = _text(ready_record, "question_text", question_id)
        answer = _text(ready_record, "expected_answer", question_id)
        explanation = _text(ready_record, "explanation", question_id)
        if question_text != _text(master_record, "corrected_mathematical_statement", question_id):
            raise DatasetValidationError(f"{question_id}: question wording differs from source reconstruction")
        if answer != _text(master_record, "final_answer", question_id) or explanation != _text(master_record, "worked_solution", question_id):
            raise DatasetValidationError(f"{question_id}: answer or worked solution differs from M10C master")
        if ready_record.get("response_type") != "FREE_RESPONSE":
            raise DatasetValidationError(f"{question_id}: unsupported response type")
        topic_slug, difficulty, skill_type = metadata[question_id]
        if TOPIC_NAMES.get(master_record.get("primary_topic")) != topic_slug:
            raise DatasetValidationError(f"{question_id}: reviewed topic mapping is inconsistent")
        # Keep source_path live in the validation flow rather than trusting a
        # filename embedded in a prose reference alone.
        if not source_path:
            raise DatasetValidationError(f"{question_id}: original source path is missing")
        imported.append(ImportItem(
            canonical_id=question_id, title=_text(ready_record, "title", question_id),
            source_reference=source_reference, question_text=question_text,
            expected_answer=answer, explanation=explanation, topic_slug=topic_slug,
            difficulty=difficulty, skill_type=skill_type,
        ))
    return sorted(imported, key=lambda item: item.canonical_id)


def load_m10e_dataset(
    dataset_path: Path,
    master_path: Path | None = None,
    verification_path: Path | None = None,
    *,
    expected_ids: frozenset[str] = M10E_IDS,
    metadata: dict[str, tuple[str, str, str]] | None = None,
    expected_count: int = 15,
) -> list[ImportItem]:
    """Validate the closed M10E source-recovery batch before database access."""
    dataset_path = dataset_path.resolve()
    root = dataset_path.parent
    ready = _read_json(dataset_path)
    master = _read_json(master_path or root / "recovery-master.json")
    verification = _read_json(verification_path or root / "verification-evidence.json")
    candidates = ready.get("items")
    if not isinstance(candidates, list) or ready.get("candidate_count") != len(candidates):
        raise DatasetValidationError("m10e-import-ready candidate_count/items are inconsistent")
    ready_by_id = _index(candidates, "stable_question_id", "m10e-import-ready")
    if frozenset(ready_by_id) != expected_ids or len(ready_by_id) != expected_count:
        raise DatasetValidationError("M10E canonical IDs do not exactly match the approved batch allow-list")
    if master.get("record_count") != len(master.get("records", [])):
        raise DatasetValidationError("M10E recovery-master record_count/records are inconsistent")
    master_by_id = _index(master.get("records"), "stable_question_id", "recovery-master")
    verification_by_id = _index(verification.get("records"), "stable_question_id", "verification-evidence")
    metadata = metadata or M10E_METADATA
    if set(metadata) != expected_ids:
        raise RuntimeError("M10E importer metadata does not cover the approved allow-list")

    imported: list[ImportItem] = []
    for question_id, ready_record in ready_by_id.items():
        if not CANONICAL_ID.fullmatch(question_id):
            raise DatasetValidationError(f"Invalid canonical ID: {question_id}")
        master_record = master_by_id.get(question_id)
        evidence_record = verification_by_id.get(question_id)
        if master_record is None or evidence_record is None:
            raise DatasetValidationError(f"{question_id}: missing M10E master/evidence record")
        if master_record.get("transcription_status") not in {"source_verified", "source_verified_with_context"}:
            raise DatasetValidationError(f"{question_id}: source transcription is not verified")
        if master_record.get("solution_status") != "verified_derived_solution" or evidence_record.get("solution_status") != "verified_derived_solution":
            raise DatasetValidationError(f"{question_id}: solution verification is insufficient")
        if master_record.get("remaining_uncertainties") is not None:
            raise DatasetValidationError(f"{question_id}: unresolved critical source uncertainty")
        source_path = _text(master_record, "original_source_path", question_id)
        page = master_record.get("source_page")
        _text(master_record, "original_question_number", question_id)
        source_evidence = _text(master_record, "source_page_evidence", question_id)
        if not isinstance(page, int) or page < 1 or not (root / source_evidence).is_file():
            raise DatasetValidationError(f"{question_id}: source-page evidence is missing")
        if not _text(evidence_record, "method", question_id) or not _text(evidence_record, "evidence", question_id):
            raise DatasetValidationError(f"{question_id}: independent verification evidence is missing")
        if not isinstance(evidence_record.get("computed"), dict) or not evidence_record["computed"]:
            raise DatasetValidationError(f"{question_id}: independent computed verification is missing")
        source_reference = _text(ready_record, "source_reference", question_id)
        if source_reference != _text(master_record, "source_reference", question_id):
            raise DatasetValidationError(f"{question_id}: source provenance differs between M10E artifacts")
        if _text(ready_record, "external_source_id", question_id) != f"{EXTERNAL_NAMESPACE}{question_id}":
            raise DatasetValidationError(f"{question_id}: external source identifier is invalid")
        question_text = _text(ready_record, "question_text", question_id)
        answer = _text(ready_record, "expected_answer", question_id)
        explanation = _text(ready_record, "explanation", question_id)
        if question_text != _text(master_record, "corrected_mathematical_statement", question_id):
            raise DatasetValidationError(f"{question_id}: question wording differs from source reconstruction")
        if answer != _text(master_record, "final_answer", question_id) or explanation != _text(master_record, "worked_solution", question_id):
            raise DatasetValidationError(f"{question_id}: answer or worked solution differs from M10E master")
        if ready_record.get("response_type") != "FREE_RESPONSE":
            raise DatasetValidationError(f"{question_id}: unsupported response type")
        topic_slug, difficulty, skill_type = metadata[question_id]
        staged_metadata = ready_record.get("metadata_for_m10f")
        if staged_metadata != {"topic_slug": topic_slug, "difficulty": difficulty, "skill_type": skill_type}:
            raise DatasetValidationError(f"{question_id}: staged M10E metadata differs from reviewed metadata")
        if TOPIC_NAMES.get(master_record.get("primary_topic")) != topic_slug:
            raise DatasetValidationError(f"{question_id}: reviewed topic mapping is inconsistent")
        if not source_path:
            raise DatasetValidationError(f"{question_id}: original source path is missing")
        imported.append(ImportItem(
            canonical_id=question_id, title=_text(ready_record, "title", question_id),
            source_reference=source_reference, question_text=question_text,
            expected_answer=answer, explanation=explanation, topic_slug=topic_slug,
            difficulty=difficulty, skill_type=skill_type,
        ))
    return sorted(imported, key=lambda item: item.canonical_id)


def load_import_batch(
    batch: str,
    dataset_path: Path,
    canonical_path: Path | None = None,
    evidence_path: Path | None = None,
    grading_path: Path | None = None,
) -> list[ImportItem]:
    """Load one of the closed, reviewed batches; unknown batches are refused."""
    if batch not in BATCHES:
        raise DatasetValidationError(f"Unknown import batch: {batch!r}")
    if batch == "m10a3":
        return load_verified_dataset(dataset_path, canonical_path, evidence_path, grading_path)
    if grading_path is not None:
        raise DatasetValidationError(f"{batch} does not accept a grading-configurations override")
    if batch == "m10c":
        return load_m10c_dataset(dataset_path, canonical_path, evidence_path)
    return load_m10e_dataset(dataset_path, canonical_path, evidence_path)


def assert_local_development_engine(engine: Engine) -> None:
    """Refuse hosted/unknown databases even when a caller mistakenly uses --apply."""
    url = engine.url
    if url.get_backend_name() != "postgresql" or url.host not in {"localhost", "127.0.0.1", "::1"} or url.database != "dmi_platform":
        raise RuntimeError("Refusing import: target must be local PostgreSQL localhost/127.0.0.1/::1 database dmi_platform.")


def _question_matches(question: Question, item: ImportItem) -> bool:
    return (
        question.external_source_id == item.external_source_id
        and question.source_reference == item.source_reference
        and question.title == item.title
        and question.difficulty == item.difficulty
        and question.response_type == item.response_type
        and question.skill_type == item.skill_type
        and question.question_text == item.question_text
        and question.expected_answer == item.expected_answer
        and question.explanation == item.explanation
        and question.topic.slug == item.topic_slug
    )


def plan_import(session: Session, items: Iterable[ImportItem], *, dataset: str, dry_run: bool) -> tuple[ImportReport, list[ImportItem]]:
    items = list(items)
    bind = session.get_bind()
    url = bind.url if isinstance(bind, Engine) else bind.engine.url
    report = ImportReport(dataset=dataset, dry_run=dry_run, target=f"{url.host}:{url.port}/{url.database}", validated=len(items))
    topics = {topic.slug: topic for topic in session.scalars(select(Topic).where(Topic.slug.in_({item.topic_slug for item in items})))}
    for item in items:
        topic = topics.get(item.topic_slug)
        if topic is None:
            report.rejected.append(f"{item.canonical_id}: required topic slug {item.topic_slug!r} does not exist")
        else:
            report.topic_distribution[item.topic_slug] = report.topic_distribution.get(item.topic_slug, 0) + 1
    response_types = set(session.scalars(select(ResponseType.code).where(ResponseType.code == "FREE_RESPONSE")))
    skills = set(session.scalars(select(SkillType.code).where(SkillType.code.in_({item.skill_type for item in items}))))
    if response_types != {"FREE_RESPONSE"}:
        report.rejected.append("Required response type FREE_RESPONSE does not exist")
    for item in items:
        if item.skill_type not in skills:
            report.rejected.append(f"{item.canonical_id}: skill {item.skill_type!r} does not exist")
    existing = {question.external_source_id: question for question in session.scalars(select(Question).where(Question.external_source_id.in_([item.external_source_id for item in items])))}
    create: list[ImportItem] = []
    for item in items:
        question = existing.get(item.external_source_id)
        if question is None:
            create.append(item)
        elif _question_matches(question, item):
            report.skipped += 1
        else:
            report.conflicts.append(f"{item.canonical_id}: external identifier exists with conflicting stored content")
    if report.rejected or report.conflicts:
        return report, []
    if dry_run:
        report.created = len(create)  # Proposed creates, not persisted writes.
    return report, create


def import_items(
    session: Session,
    items: Iterable[ImportItem],
    *,
    dataset: str,
    dry_run: bool = True,
    post_write_check: Callable[[Session, list[ImportItem]], None] | None = None,
) -> ImportReport:
    """Dry-run or atomically create a batch; never updates an existing question."""
    report, create = plan_import(session, items, dataset=dataset, dry_run=dry_run)
    if report.rejected or report.conflicts:
        return report
    if dry_run:
        return report
    # Reads in plan_import open SQLAlchemy's implicit transaction. Close it
    # before starting the single all-or-nothing write transaction.
    session.rollback()
    try:
        with session.begin():
            topics = {topic.slug: topic for topic in session.scalars(select(Topic).where(Topic.slug.in_({item.topic_slug for item in create})))}
            for item in create:
                session.add(Question(
                    external_source_id=item.external_source_id, source_reference=item.source_reference,
                    topic=topics[item.topic_slug], title=item.title, difficulty=item.difficulty,
                    response_type=item.response_type, skill_type=item.skill_type,
                    question_text=item.question_text, expected_answer=item.expected_answer,
                    correct_boolean=None, explanation=item.explanation, is_active=True,
                ))
            session.flush()
            if post_write_check is not None:
                post_write_check(session, items)
        report.created = len(create)
    except Exception:
        session.rollback()
        raise
    return report
