"""Separately authorized, all-or-nothing production import for the 52 DMI questions."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from sqlalchemy.orm import Session

from app.importers.dmi_verified import BATCHES, DatasetValidationError, import_items, load_import_batch, plan_import
from app.importers.production_control import (
    INSPECTION_ACKNOWLEDGEMENT,
    WRITE_ACKNOWLEDGEMENT,
    authorize_production_import,
    get_production_import_engine,
    load_backup_evidence,
    require_production_revision,
    verify_persisted_items,
)


MANIFEST_FIELDS = {
    "m10a3": ("dataset", "canonical_solutions", "verification_evidence", "grading_configurations"),
    "m10c": ("dataset", "canonical_solutions", "verification_evidence"),
    "m10e": ("dataset", "canonical_solutions", "verification_evidence"),
}


def load_manifest(path: Path) -> dict[str, dict[str, Path]]:
    """Accept only the three closed batches and their expected artifact names."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Production manifest must be a readable JSON document.") from exc
    if not isinstance(raw, dict) or set(raw) != set(MANIFEST_FIELDS):
        raise RuntimeError("Production manifest must contain exactly m10a3, m10c, and m10e.")
    root = path.resolve().parent
    result: dict[str, dict[str, Path]] = {}
    for batch, fields in MANIFEST_FIELDS.items():
        values = raw.get(batch)
        if not isinstance(values, dict) or set(values) != set(fields):
            raise RuntimeError(f"Production manifest has an invalid {batch} artifact set.")
        expected_names = BATCHES[batch].required_artifacts
        resolved: dict[str, Path] = {}
        for field, expected_name in zip(fields, expected_names, strict=True):
            value = values[field]
            if not isinstance(value, str) or Path(value).name != expected_name:
                raise RuntimeError(f"Production manifest has an unexpected {batch} artifact name.")
            candidate = (root / value).resolve()
            if root not in candidate.parents or not candidate.is_file():
                raise RuntimeError(f"Production manifest references a missing or out-of-root artifact for {batch}.")
            resolved[field] = candidate
        result[batch] = resolved
    return result


def load_all_batches(manifest: dict[str, dict[str, Path]]):
    loaded = {}
    for batch, paths in manifest.items():
        loaded[batch] = load_import_batch(
            batch,
            paths["dataset"],
            paths.get("canonical_solutions"),
            paths.get("verification_evidence"),
            paths.get("grading_configurations"),
        )
        if len(loaded[batch]) != BATCHES[batch].expected_count:
            raise RuntimeError(f"Verified {batch} item count does not match the closed registry.")
    all_items = [item for batch in ("m10a3", "m10c", "m10e") for item in loaded[batch]]
    if len(all_items) != 52 or len({item.external_source_id for item in all_items}) != 52:
        raise RuntimeError("Production import must contain exactly 52 unique approved questions.")
    return loaded, all_items


def safe_report(*, dry_run: bool, reports: dict[str, object], total: object, verified: bool) -> str:
    """Never print connection strings, artifact paths, or backup-attestation content."""
    def compact(report):
        data = asdict(report)
        return {key: data[key] for key in ("dry_run", "validated", "created", "skipped", "conflicts", "rejected", "topic_distribution")}
    return json.dumps({"dry_run": dry_run, "batches": {name: compact(report) for name, report in reports.items()}, "total": compact(total), "post_import_verified": verified}, indent=2, sort_keys=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="Reviewed manifest for the exact 52 approved artifacts.")
    parser.add_argument("--backup-evidence", type=Path, required=True, help="Non-secret production backup/restore attestation JSON.")
    parser.add_argument("--production-import-ack", required=True, help="Required explicit inspection acknowledgement.")
    parser.add_argument("--apply", action="store_true", help="Defaults to dry-run; writes require the second acknowledgement.")
    parser.add_argument("--production-write-ack", help="Required only with --apply.")
    args = parser.parse_args()
    try:
        manifest = load_manifest(args.manifest)
        batches, all_items = load_all_batches(manifest)
        engine = get_production_import_engine()
        authorize_production_import(
            engine,
            inspection_acknowledgement=args.production_import_ack,
            backup_evidence=load_backup_evidence(args.backup_evidence),
            apply=args.apply,
            write_acknowledgement=args.production_write_ack,
        )
        with Session(engine) as session:
            require_production_revision(session)
            plans = {name: plan_import(session, items, dataset=f"production:{name}", dry_run=True)[0] for name, items in batches.items()}
            if any(report.conflicts or report.rejected for report in plans.values()):
                print(safe_report(dry_run=True, reports=plans, total=plan_import(session, all_items, dataset="production", dry_run=True)[0], verified=False))
                raise SystemExit(2)
            total = import_items(
                session,
                all_items,
                dataset="production:closed-registry-52",
                dry_run=not args.apply,
                post_write_check=verify_persisted_items if args.apply else None,
            )
            if total.conflicts or total.rejected:
                print(safe_report(dry_run=not args.apply, reports=plans, total=total, verified=False))
                raise SystemExit(2)
            print(safe_report(dry_run=not args.apply, reports=plans, total=total, verified=args.apply))
    except (DatasetValidationError, RuntimeError) as exc:
        raise SystemExit(f"Production import refused: {exc}") from None


if __name__ == "__main__":
    main()
