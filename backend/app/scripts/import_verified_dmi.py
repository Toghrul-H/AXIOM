"""Explicit local-only importer for closed, cross-verified DMI batches."""
from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import get_engine
from app.importers.dmi_verified import (
    DatasetValidationError,
    BATCHES,
    ImportConflictError,
    assert_local_development_engine,
    import_items,
    load_import_batch,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", choices=sorted(BATCHES), default="m10a3", help="Closed reviewed batch identifier (default: m10a3).")
    parser.add_argument("--dataset", type=Path, required=True, help="Closed-batch ready JSON (M10A.3, M10C, or M10E).")
    parser.add_argument("--canonical-solutions", type=Path, help="M10A.3 canonical solutions, or an M10C/M10E recovery master.")
    parser.add_argument("--verification-evidence", type=Path, help="M10A.3 verification evidence, M10C solution verification, or M10E verification evidence.")
    parser.add_argument("--grading-configurations", type=Path)
    parser.add_argument("--apply", action="store_true", help="Write only after explicit local-development safety checks. Defaults to dry-run.")
    args = parser.parse_args()
    try:
        items = load_import_batch(args.batch, args.dataset, args.canonical_solutions, args.verification_evidence, args.grading_configurations)
        engine = get_engine()
        assert_local_development_engine(engine)
        with Session(engine) as session:
            report = import_items(session, items, dataset=f"{args.batch}:{args.dataset.resolve()}", dry_run=not args.apply)
        print(report.json())
        if report.conflicts or report.rejected:
            raise SystemExit(2)
    except (DatasetValidationError, ImportConflictError, RuntimeError) as exc:
        raise SystemExit(f"Import refused: {exc}") from None


if __name__ == "__main__":
    main()
