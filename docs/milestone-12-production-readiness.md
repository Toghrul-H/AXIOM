# M12 Production Readiness Audit

Audited against local source at `033c8d6590f1b9533ece4e021356ed99cb9aba7b` plus the M12 changes listed below. This audit did not connect to Neon, Render, Vercel, Brevo, or any other production service.

## Architecture and safeguards

The browser uses the Next.js same-origin API layer, which forwards authenticated requests to the FastAPI service. FastAPI uses PostgreSQL through SQLAlchemy/Alembic. Authentication is an opaque HttpOnly session cookie, with server-side session hashing and Argon2id password hashes. State-changing requests require CSRF validation; origin and fetch-site checks provide an additional browser boundary. Role dependencies gate student, staff, and staff-management routes; attempt, practice-quiz, progress, learning-history, grading, and Question Bank queries apply ownership or role predicates.

The application has a closed, provenance-checked DMI importer (`m10a3`, `m10c`, and `m10e`), a separate question/quiz system, manual grading, and an offline bounded Tectonic compiler. The compiler is limited by mode, template allow-list, timeout, output size, and a process-local concurrency limit. The Docker image uses a non-root user and one Uvicorn worker.

No repository CI pipeline was found under `.github` or `.gitlab`. This is a release-process gap, not evidence about any provider-side configuration.

## Findings and local fixes

| Area | Evidence | Result |
| --- | --- | --- |
| PostgreSQL transport | The URL builder previously relied on libpq's default SSL mode. | Added `DATABASE_SSLMODE`, passed to the SQLAlchemy URL, with `require` documented for Neon production. Local default remains `prefer`. |
| Readiness | The root endpoint checked only process liveness. | Added `GET /health`, which executes `SELECT 1` through the configured session and returns only `{"status":"ok"}`. SQL errors retain the application's generic 503 handling. |
| Migration compatibility | `0013` adds nullable provenance fields; `0014` adds a default-false practice flag, nullable owner, foreign key, indexes, and consistency check. | Added an isolated-schema rehearsal from `0012` through `0014`, including existing user/quiz data and a downgrade/upgrade cycle. Existing base fields remained unchanged. |

The configuration test verifies the TLS mode is included without rendering the password. The health test verifies the database-backed response and `Cache-Control: no-store`.

## Security and functional assessment

Reviewed code and regression tests cover login/logout/session invalidation, inactive and unverified accounts, Argon2id hashing, CSRF/origin rejection, staff/student RBAC, practice ownership, attempt ownership, grading access, and hidden-question/solution boundaries. API client requests use same-origin credentials; the proxy forwards cookies and CSRF headers rather than exposing a token to client JavaScript. Sanitized email/compiler error paths avoid secret, token, and email-body logging.

The practice implementation reuses the normal quiz/attempt lifecycle. Private practice quizzes require an owner and cannot be represented as ordinary public quizzes. Existing pagination limits the main Question Bank and attempt history paths. Progress and learning-summary services load related attempts with `selectinload`; the learning summary also makes a second bounded attempt query for topic rows. It is not a demonstrated bottleneck, but should be profiled with representative production data before scalability claims.

Known security/reliability limits retained by design: rate limiting is process-local, there is no MFA/password-reset flow, no repository CI gate, no background PDF queue, and no live observability/backup/restore evidence in the repository. The source does not define explicit CSP/security-header policy; provider headers were intentionally not inspected. These require operator review before a public launch.

## Database and question-import readiness

The local database reports Alembic `0014 (head)` and `alembic check` found no model/schema drift. The tested upgrade path is `0012 → 0013 → 0014`; deployment must migrate before the new backend serves traffic. The migrations are additive, but downgrading `0013` or `0014` drops the corresponding columns and can lose post-release provenance/practice metadata. Rollback should therefore normally retain the newer schema and restore a code-compatible application.

The verified-question importer deliberately fails closed unless it targets the local `dmi_platform` loopback database. It must not be weakened for production. A future authorized import needs a separately reviewed, least-privileged controlled runner that reuses the exact closed batch registry and artifact set, verifies a production backup and current schema, runs batches in order (`m10a3`, `m10c`, `m10e`), records dry-run/conflict results, and performs post-import ID/count checks. It must never copy local users, attempts, practice data, or unrelated questions.

## Test evidence

| Check | Result |
| --- | --- |
| Focused M12 config, migration, and health tests | 3 passed (two pre-existing framework deprecation warnings) |
| Full backend suite with isolated PostgreSQL-schema tests enabled | 273 passed |
| Alembic current / heads / drift check | `0014 (head)` / `0014 (head)` / no new upgrade operations |
| Prettier check | passed |
| ESLint | passed |
| TypeScript `--noEmit` | passed |
| Next.js production Webpack build | passed |

No frontend unit-test script or browser-test package is declared in `frontend/package.json`; none was invented for this audit.

## Browser E2E attempt

A real local browser was launched against `http://127.0.0.1:3000/login`. The pre-existing local demo credential did not authenticate, so it was not altered or inspected. A disposable database named `dmi_m12_e2e` was then requested for the required student-to-teacher workflow; the local application role was denied `CREATE DATABASE` by PostgreSQL before any database was created. To preserve `dmi_platform` and its users, no browser fixture was created in the development schema.

Consequently, the authenticated student-practice, teacher-grading, student-review, responsive, network-failure, and empty-topic browser scenarios were **attempted but not executed**. This is a local test-environment permission blocker, not a successful E2E result. The automated isolated PostgreSQL tests did run. An operator can resolve it by supplying a disposable local test database or granting a dedicated E2E role only the ability to create/drop a database, then running the documented workflow before release.

## Production readiness decision

**NO-GO for production deployment today.** Local code and automated gates are healthy, but the following mandatory release evidence is absent:

1. An approved immutable, registry-accessible `TECTONIC_RESOURCES_IMAGE`. The Dockerfile deliberately requires an explicit digest-pinned build argument, so a clean remote build cannot accidentally use a local proof-of-concept image.
2. An authorized confirmation of the live Render/Vercel/Neon settings, current production revision, service health path, resource limits, backup/restore evidence, Brevo sender, and Vercel PDF timeout.
3. Successful disposable-browser E2E evidence for the full student-to-teacher workflow.
4. A controlled, separately approved production importer procedure if the 52 verified questions must be introduced.

The companion [deployment runbook](milestone-12-deployment-runbook.md) defines release stops and recovery actions. No production resource was modified in M12.
