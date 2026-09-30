# Milestone 3 verification

Verified locally on 20 September 2026 with Python 3.11.9, PostgreSQL 18.6,
Node.js 24.19.0 and Next.js 16.3.5. No new dependency was required for this milestone.

## Database and backend

- Existing database inspected before migration: zero questions; ignored audit snapshot saved.
- `alembic upgrade head` applied `0002`; no database reset or startup `create_all`.
- `alembic current`: `0002 (head)`.
- `alembic check`: no new upgrade operations detected.
- `RUN_POSTGRES_TESTS=1` + `python -m pytest -q`: **41 passed**, two dependency deprecation warnings.
- Tests cover all four response types, invalid configurations, strict Booleans, duplicate
  and foreign option IDs, missing questions, multiple PS/tag associations, all filter
  dimensions, combined filtering, pagination totals and literal search characters.
- Tests also cover independent PostgreSQL persistence, atomic invalid PATCH behavior,
  option identity/reordering/type conversion, deletion cascades, objective checks for
  correct/wrong/partial/extra choices and reference-only free response.
- Isolated temporary PostgreSQL schema verifies upgrading three legacy rows: answers,
  text, IDs, timestamps, custom topic, topic aliases and options preserved. Only the
  test schema is removed afterwards; course tables are untouched.

## Browser and PostgreSQL verification

With backend and frontend running, used the Teacher Question Bank to create four
explicitly labelled disposable browser questions: FREE_RESPONSE, SINGLE_CHOICE,
MULTIPLE_SELECT and TRUE_FALSE. The free-response example had two problem sets and
three suitability tags. Choice examples had one and two correct options respectively.

- Reloaded and verified all four remained visible.
- Independently queried PostgreSQL to confirm four persisted records and their answers,
  option flags and associations.
- Edited all four explanations and difficulties; made the true/false example inactive.
- Verified combined text + parent topic + PS5 + difficulty + response type + skill +
  MIDTERM filtering returned exactly the expected child-topic question.
- Verified a mismatched difficulty produced an empty result and inactive filtering
  returned only the inactive example.
- Opened delete confirmation, cancelled and verified the question remained; then
  confirmed deletion of that disposable example and verified it disappeared.
- Independently checked edited values and the deleted ID's absence in PostgreSQL.
- Removed the other three disposable browser records; retained the seven `[DEV]` seeds.
- Re-ran the seed command: zero additions, existing matching titles unchanged.

## Frontend checks

Prettier formatting, ESLint, TypeScript `--noEmit` and Next.js production build passed.
The shared typed client, dynamic forms, filters, teacher preview and student hierarchy
use the new API. Root/student/teacher routes build successfully. Browser preview is
left on the Question Bank for review.

## Remaining limits and warnings

- Starlette reports deprecations for its HTTPX TestClient integration and AnyIO portal
  alias; tests still pass. The existing ESLint 9 dependency is registry-deprecated;
  lint passes. Resolve these in a separate toolchain maintenance change.
- Local unauthenticated preview only; teacher role links grant no real permissions.
- Legacy `UNSPECIFIED` skills require later content classification when present.
- Downgrade from `0002` intentionally refuses potentially lossy conversion.
- Topic maintenance is through reviewed data migrations, with no taxonomy admin UI.
- Text search uses substring matching; reconsider full-text/trigram indexes if real
  content volume warrants it. No premature search infrastructure was added.
- Before persistent attempts/assessments, design question revision or snapshot semantics.
- Development examples and their problem-set mappings are not official course material.

See [architecture](milestone-3-architecture.md) for the future learning-feedback notice,
manual-review considerations and migration mapping. See [backend startup](../backend/README.md)
and [frontend startup](../frontend/README.md) for exact commands. Existing server startup
commands remain unchanged; migrate before starting and optionally run the seed command.
