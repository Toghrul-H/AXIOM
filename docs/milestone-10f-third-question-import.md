# M10F — Third Verified DMI Question Import

M10F registers the closed `m10e` batch in the private, local-only DMI importer.
It contains exactly 15 independently derived and verified `FREE_RESPONSE`
questions recovered by M10E. The importer is not reachable through an HTTP
endpoint and is never run by application startup or Alembic.

## Closed-batch validation

`m10e` has an explicit 15-ID allow-list and separately curated
topic/difficulty/skill metadata. Its adapter cross-checks every ready record
against `recovery-master.json` and `verification-evidence.json`. It requires:

- a source-verified transcription and no unresolved critical uncertainty;
- original source path, page, exercise number, and an existing external
  source-page evidence file;
- matching source reference, question text, final answer, and worked solution;
- independently verified derived-solution status plus non-empty method,
  evidence, and computed result;
- `FREE_RESPONSE` and an exact match between staged and code-reviewed metadata.

The existing `m10a3` and `m10c` adapters and allow-lists are unchanged. Unknown
batch names remain rejected. All imported questions use the existing manual
grading workflow; no mathematical answer is auto-graded.

## Local command

From `backend/`, dry-run first:

```powershell
.\.venv\Scripts\python.exe -m app.scripts.import_verified_dmi --batch m10e --dataset "C:\Users\Toghrul\Desktop\dmi-analysis\m10e-recovery\m10e-import-ready.json" --canonical-solutions "C:\Users\Toghrul\Desktop\dmi-analysis\m10e-recovery\recovery-master.json" --verification-evidence "C:\Users\Toghrul\Desktop\dmi-analysis\m10e-recovery\verification-evidence.json"
```

Add `--apply` only after the local-only guard confirms
`localhost:5432/dmi_platform` and the dry-run reports no conflict or rejection.

## M10F local verification

Pre-import snapshot: Alembic `0013 (head)`, 48 questions, 37 prior verified
imports (23 M10A.3 plus 14 M10C), 11 unrelated questions, and 6 users.

The M10E dry-run validated 15 and proposed 15 creates with zero conflicts or
rejections. The explicit local apply created 15 rows transactionally. A second
apply created zero and skipped all 15. Readback matched every staged external
ID, provenance, statement, answer, explanation, topic, and `FREE_RESPONSE`
configuration.

Final local state: 63 questions, 52 verified DMI imports, 11 unrelated
questions, and 6 users. M10E's distribution is 10 Binary Relations, 2
Functions, 1 Sets, 1 Complex Numbers, and 1 Combinatorics.

Focused importer tests passed both without database integration (`21 passed,
5 skipped`) and with isolated temporary PostgreSQL schemas (`26 passed`). Those
schemas are created with unique names and dropped after each test; the public
development schema is not used by write-oriented tests.

## Future batches

Future batches must add a separate exact ID allow-list, code-reviewed metadata,
an adapter-specific evidence contract, focused unit tests, isolated-schema
integration tests, a local dry-run, and explicit local application. They must
not loosen an existing adapter or import from a hosted database.
