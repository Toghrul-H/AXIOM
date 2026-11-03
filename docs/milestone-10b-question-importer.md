# M10B/M10D — Verified DMI Question Importer

The importer is a private, explicit command for closed reviewed batches. It is
never invoked at startup, by Alembic, or through an HTTP endpoint. M10B defined
the 23-record M10A.3 batch; M10D added the separately validated 14-record M10C
batch; M10F adds the separately validated 15-record M10E batch. Original course
PDFs are never copied into the repository.

## Preconditions

Apply revision `0013` with the normal migration process. Each closed batch has
an explicit code-reviewed ID allow-list, expected count, topic/skill mapping,
and evidence adapter. M10A.3 cross-validates its four analysis artifacts; M10C
cross-validates its import-ready JSON, recovered master, deterministic solution
verification, and external source-page evidence; M10E additionally requires a
source-verified transcription, original exercise number, and exact staged
metadata match. All batches currently require
`FREE_RESPONSE` and manual grading. The target must be PostgreSQL on
`localhost`, `127.0.0.1`, or `::1`, with database name `dmi_platform`; hosted
targets are refused.

Run from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.scripts.import_verified_dmi --dataset "C:\Users\Toghrul\Desktop\dmi-analysis\m10a3-solutions\ready-for-m10b.json"
```

The default command is a dry run: it reports topic mappings and proposed
operations and performs zero writes. After reviewing that report, explicitly
apply it:

```powershell
.\.venv\Scripts\python.exe -m app.scripts.import_verified_dmi --dataset "C:\Users\Toghrul\Desktop\dmi-analysis\m10a3-solutions\ready-for-m10b.json" --apply
```

M10C requires explicit batch selection:

```powershell
.\.venv\Scripts\python.exe -m app.scripts.import_verified_dmi --batch m10c --dataset "C:\Users\Toghrul\Desktop\dmi-analysis\m10c-recovery\m10c-import-ready.json"
```

M10E requires explicit batch selection and its two cross-check artifacts:

```powershell
.\.venv\Scripts\python.exe -m app.scripts.import_verified_dmi --batch m10e --dataset "C:\Users\Toghrul\Desktop\dmi-analysis\m10e-recovery\m10e-import-ready.json" --canonical-solutions "C:\Users\Toghrul\Desktop\dmi-analysis\m10e-recovery\recovery-master.json" --verification-evidence "C:\Users\Toghrul\Desktop\dmi-analysis\m10e-recovery\verification-evidence.json"
```

Run the same `--apply` command again to verify idempotency; matching records
are skipped. A reused external identifier with different stored content is a
conflict and aborts without overwriting any question. Any invalid source file,
missing evidence, unknown topic/skill, or conflict stops the whole batch before
writes. New records are written in one transaction.

Each imported `Question` stores an `external_source_id` such as
`M10A3:M10A-da76c4d2f484` and its source reference. These private provenance
fields prevent text-based deduplication. The imported questions use existing
`FREE_RESPONSE` manual grading; their reference answers and worked solutions
are not automatically graded and only become student-visible through the
existing submitted-attempt review flow.

## Verified local import (M10B.1)

Revision `0013` was applied to the local `dmi_platform` database. A read-only
integrity check found 23 imported records with 23 unique external identifiers,
no missing provenance, no missing answers or explanations, and no non-free
response types. The actual source-backed distribution is:

- Binary Relations: 9
- Sets: 9
- Combinatorics: 3
- Logic: 2

The prior `7/3/5/6` report was not a question count: it was the database topic
IDs emitted under the old, misleading `topic_mappings` diagnostic key. The
importer now reports `topic_distribution`, which counts records by topic.

The subsequent dry run validated 23 records, proposed zero creates, skipped 23
existing exact matches, and reported zero conflicts or rejections. It performs
no writes.

Focused isolated-schema tests cover valid import, idempotency, invalid and
duplicate source identifiers, conflict/rollback behavior, provenance, and the
full imported free-response API flow: staff listing/filtering/detail, quiz
selection, student submission, ownership and CSRF denial, post-submission
solution visibility, and Lecturer manual grading. The local development tables
are not used by those tests.

The frontend renders imported inline `$...$` notation with KaTeX in the staff
question bank, student quiz, submitted review, and manual-grading views.
Untrusted KaTeX commands remain disabled. Component tests cover normal math
rendering and inert untrusted markup; no browser run was performed in M10B.1.

At M10B.1 completion: the backend suite passed (`111 passed, 140 skipped`),
the focused isolated PostgreSQL importer/API suite passed (`9 passed`), and the
frontend Node tests passed (`70 passed`). Formatting, ESLint, TypeScript, and
the production build passed. The build command explicitly uses Next.js
Webpack (`next build --webpack`): default Turbopack was unable to launch its
CSS worker on this Windows machine, while the Webpack production build
completed successfully. This preserves all build checks and is the repeatable
local/CI procedure.

## Limitations and production prerequisites

The importer is intentionally local-development-only and must never be aimed
at a hosted database. Do not import the 102 blocked records. Before a future
deployment, apply revision `0013` through the normal controlled migration
process, install the locked frontend dependencies (including KaTeX), and run
the configured Webpack production build. Any release decision still requires
the normal deployment review; M10B.1 made no production connection, deployment,
or browser-based manual verification.

## Future batches

Do not modify an allow-list casually. A new batch needs separately reviewed
canonical IDs, cross-validated source/solution/evidence artifacts, deliberate
topic/skill/difficulty mappings, focused tests, and a new explicit registry
entry plus evidence adapter. Never use this command for a hosted database.
