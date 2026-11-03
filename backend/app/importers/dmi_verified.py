"""Validated, atomic M10A.3 DMI-question import support.

This module deliberately has no route or startup hook.  The CLI is the only
entry point for importing an external, reviewed dataset.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re
from typing import Any, Iterable

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


def import_items(session: Session, items: Iterable[ImportItem], *, dataset: str, dry_run: bool = True) -> ImportReport:
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
        report.created = len(create)
    except Exception:
        session.rollback()
        raise
    return report
