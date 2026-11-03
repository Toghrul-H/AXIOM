# M10D — Second Verified Question Import

## Closed multi-batch design

`app.importers.dmi_verified` has a closed `BATCHES` registry. A batch has a
stable identifier, exact canonical-ID allow-list, expected count, reviewed
topic/difficulty/skill metadata, and named required artifacts. The CLI defaults
to the original `m10a3` batch for backwards compatibility; M10C must be named
explicitly with `--batch m10c`.

The importer remains local-only, CLI-only, transactional, and idempotent. It
does not accept an arbitrary ready JSON. `m10a3` retains its canonical solution,
verification-evidence, and grading-configuration checks. `m10c` uses an
explicit adapter which requires matching recovered wording, answer, solution,
source path/page/render evidence, deterministic independent-verification
record, verified status, and no unresolved critical uncertainty.

## Commands

Run from `backend/` after the local environment is configured:

```powershell
.\.venv\Scripts\python.exe -m app.scripts.import_verified_dmi --batch m10a3 --dataset "C:\Users\Toghrul\Desktop\dmi-analysis\m10a3-solutions\ready-for-m10b.json"
.\.venv\Scripts\python.exe -m app.scripts.import_verified_dmi --batch m10c --dataset "C:\Users\Toghrul\Desktop\dmi-analysis\m10c-recovery\m10c-import-ready.json"
```

Add `--apply` only after reviewing a dry run and confirming a local
`localhost:5432/dmi_platform` target. The host/database guard rejects hosted
targets. Neither batch is run by application startup or Alembic.

## M10C composition and limitations

The reviewed M10C batch has 14 `FREE_RESPONSE` questions: 2 Binary Relations,
11 Combinatorics, and 1 Complex Numbers. They use the established manual
grading workflow. The remaining 88 M10C records are deliberately excluded.

Future batches require a new closed registry entry, adapter-specific evidence
validation, explicit reviewed metadata, unit tests, isolated PostgreSQL tests,
and a dry run. Do not relax an existing batch's allow-list or import from a
hosted database.

## Local M10D verification result

Before the write, the local target was confirmed as
`localhost:5432/dmi_platform` at Alembic revision `0013 (head)`: 34 questions,
23 existing verified DMI imports, 11 unrelated questions, and 6 users. The
M10C dry run validated 14, proposed 14 creates, and reported no conflicts or
rejections. The M10A.3 dry run validated 23 and skipped its 23 exact matches.

The explicit local M10C apply created 14 records with no conflict or rejection.
Readback matched every imported question's external ID, provenance, statement,
answer, explanation, topic, response type, skill, and difficulty against the
batch artifacts. The final local count is 48 questions: 37 verified DMI imports
and 11 unrelated questions; the 6 users remain unchanged. A second explicit
M10C apply created zero and skipped all 14.

Focused importer tests passed (`11 passed, 4 skipped` without local
integration; `15 passed` with the isolated temporary-schema integration run).
The full backend suite passed (`116 passed, 141 skipped`) and Alembic reported
no schema drift. No frontend source changed in M10D; the existing M10B.1
KaTeX and imported-free-response workflow tests remain the integration coverage
for staff display, quiz submission, manual grading, and solution visibility.
