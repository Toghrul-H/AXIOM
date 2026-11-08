"""Explicitly guarded runner for an approved production DMI import.

It is deliberately separate from the local-only CLI. It defaults to a dry run
but still requires an explicit target/backup acknowledgement before connecting.
Never use it without the release owner's written authorization.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import get_engine
from app.importers.dmi_verified import BATCHES, import_items, load_import_batch
from app.importers.production_control import (
    INSPECTION_ACKNOWLEDGEMENT,
    WRITE_ACKNOWLEDGEMENT,
    authorize_production_import,
    load_backup_evidence,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", choices=sorted(BATCHES), required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--canonical-solutions", type=Path)
    parser.add_argument("--verification-evidence", type=Path)
    parser.add_argument("--grading-configurations", type=Path)
    parser.add_argument("--backup-evidence", type=Path, required=True)
    parser.add_argument("--authorization", required=True, help=f"Must exactly equal {INSPECTION_ACKNOWLEDGEMENT}")
    parser.add_argument("--apply", action="store_true", help="Write only after all guards; default is dry-run.")
    parser.add_argument("--write-authorization", help=f"Required with --apply: {WRITE_ACKNOWLEDGEMENT}")
    args = parser.parse_args()
    try:
        engine = get_engine()
        authorize_production_import(
            engine,
            inspection_acknowledgement=args.authorization,
            backup_evidence=load_backup_evidence(args.backup_evidence),
            apply=args.apply,
            write_acknowledgement=args.write_authorization,
        )
        items = load_import_batch(
            args.batch, args.dataset, args.canonical_solutions,
            args.verification_evidence, args.grading_configurations,
        )
        with Session(engine) as session:
            report = import_items(session, items, dataset=f"{args.batch}:{args.dataset.resolve()}", dry_run=not args.apply)
        print(report.json())
        if report.conflicts or report.rejected:
            raise SystemExit(2)
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(f"Import refused: {exc}") from None


if __name__ == "__main__":
    main()
