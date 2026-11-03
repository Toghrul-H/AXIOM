"""Explicit local-only importer for the 23 cross-verified M10A.3 questions."""
from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import get_engine
from app.importers.dmi_verified import (
    DatasetValidationError,
    ImportConflictError,
    assert_local_development_engine,
    import_items,
    load_verified_dataset,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True, help="Path to M10A.3 ready-for-m10b.json")
    parser.add_argument("--canonical-solutions", type=Path)
    parser.add_argument("--verification-evidence", type=Path)
    parser.add_argument("--grading-configurations", type=Path)
    parser.add_argument("--apply", action="store_true", help="Write only after explicit local-development safety checks. Defaults to dry-run.")
    args = parser.parse_args()
    try:
        items = load_verified_dataset(args.dataset, args.canonical_solutions, args.verification_evidence, args.grading_configurations)
        engine = get_engine()
        assert_local_development_engine(engine)
        with Session(engine) as session:
            report = import_items(session, items, dataset=str(args.dataset.resolve()), dry_run=not args.apply)
        print(report.json())
        if report.conflicts or report.rejected:
            raise SystemExit(2)
    except (DatasetValidationError, ImportConflictError, RuntimeError) as exc:
        raise SystemExit(f"Import refused: {exc}") from None


if __name__ == "__main__":
    main()
