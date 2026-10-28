# AXIOM Developer Handover

Repository review: 28 October 2026. This guide describes source behavior; live deployment state is owner-reported. Start with the [README](../README.md), [user guide](user-guide.md) and [deployment guide](production-deployment.md).

## Architecture and code map

| Location                                          | Responsibility                                                                                |
| ------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `backend/app/main.py`, `config.py`, `database.py` | FastAPI assembly, environment settings, lazy SQLAlchemy engine/session dependency             |
| `backend/app/routers/`                            | Questions/metadata, quizzes/attempts, authentication/users, progress, grading, assessments    |
| `backend/app/*models.py`, `*schemas.py`           | SQLAlchemy relationships/constraints and Pydantic request/response validation                 |
| `backend/app/services/`                           | Grading, progress, quiz snapshots, verification-token lifecycle and SMTP/Brevo delivery       |
| `backend/app/document_generation/`                | Shared document context, seven trusted templates, LaTeX escaping, draft AST, bounded compiler |
| `backend/app/scripts/`                            | Explicit operator account administration and guarded local demo seeding                       |
| `backend/alembic/versions/`                       | Ordered revisions 0001–0012; no automatic table creation                                      |
| `frontend/src/app/`                               | App Router pages, same-origin route handlers and shared styling                               |
| `frontend/src/components/`                        | Role-aware shell, editors, quizzes, progress, grading and document workspace                  |
| `frontend/src/lib/`                               | Authenticated clients, metadata, snapshot/preview/download helpers                            |
| `backend/tests/`, `frontend/tests/`               | Pytest unit/integration tests and Node test-runner regression tests                           |

Requests go Browser → Next.js `/api` → FastAPI → PostgreSQL. `API_BASE_URL` is server-side. Auth/users/grading/assessment route handlers use explicit allowlists, forward cookies and CSRF/origin headers, reject upstream redirects and disable caching. Question/metadata/quiz/student paths use Next rewrites. The PDF handler streams the response body and attachment header. Do not replace these paths with browser requests to the backend origin.

## Data and security invariants

Question metadata normalizes topics, response types, skills and associations. Quiz attempts store immutable question/option/point/topic/skill snapshots; editing source questions must not alter historical work. Only owners may access Student attempts and `/student/progress/me`. Staff grading reads submitted snapshots. Objective accuracy excludes FREE_RESPONSE and manual grades; historical unattributed topic/skill activity is represented separately.

Public registration normalizes email, accepts only exact `inf.elte.hu`, creates an unverified Student, and rolls back if initial email delivery fails. Verification tokens are random, stored hashed, single-use, expire in one hour and are superseded on resend; resend responses avoid account enumeration. Passwords use Argon2id. Sessions are random HttpOnly cookies, hashes stored server-side, SameSite=Lax, Secure in production. The CSRF token is restored from `/auth/me` into frontend memory. Role/status changes revoke sessions. Allowed-origin checks and backend RBAC remain authoritative.

Staff (Demonstrator/Lecturer/Admin) manage questions/quizzes and manual grades. Lecturer/Admin manage assessment documents. User-management transitions are deliberately narrower; see the [role table](user-guide.md). Protected accounts are hidden/immutable through public management APIs. Authentication rate limiting and PDF concurrency limits are process-local.

## Local setup

Use Python 3.11, local PostgreSQL, Node compatible with `frontend/package.json` and pnpm 11.19.0. Do not use production connection settings for development or tests. From the repository root in PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Privately configure the local `DATABASE_*` variables in the ignored file, then:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

In another terminal from the root:

```powershell
cd frontend
pnpm install --frozen-lockfile
if (!(Test-Path .env.local)) { Copy-Item .env.example .env.local }
pnpm dev
```

Use `http://127.0.0.1:3000`; Swagger is `http://127.0.0.1:8000/docs`. Real registration requires configured email delivery. For explicit local demo setup, use `python -m app.scripts.seed_demo_users --local-development` only after configuring its enable flag and private password variables. It is never a startup task.

Operator commands from the backend environment: `python -m app.scripts.system_accounts create-admin` creates the first protected Admin; `create-system-admin` deliberately permits an additional protected Admin. `protect --user-id ID` preserves an existing eligible account's role/password, verifies/protects it and revokes sessions. All prompt for confirmation; creation prompts privately for a password. These are privileged maintenance operations, not registration alternatives for students.

## Testing and migrations

From `backend`, run `.\.venv\Scripts\python.exe -m pytest -q` for the default suite; PostgreSQL tests skip without opt-in. For the full suite, privately configure a disposable **local** database, migrate it, set `$env:RUN_POSTGRES_TESTS='1'`, run the same command, then `Remove-Item Env:RUN_POSTGRES_TESTS`. The guard accepts localhost/loopback hosts only. Do not tunnel production through localhost to bypass it. Fixtures insert/delete records, can advance sequences and create/drop isolated schemas. Email transports are mocked; tests must not send real messages.

From `frontend`:

```powershell
node --test tests/*.test.mjs
pnpm format:check
pnpm lint
pnpm typecheck
pnpm build
```

Node tests use transpiled components/mocks; they are not full browser end-to-end coverage. Real Tectonic compilation needs the documented image/resources; mock compiler tests alone do not prove font/package availability.

Use `alembic current`, `alembic heads` and `alembic check` in an explicitly selected database environment. Current source head is 0012. Revisions 0010–0012 add assessment tables, optional writing times and shared policies/deadlines. They do not rewrite existing quiz/user data. Review migrations and backup before applying them; never use automatic `create_all` or `stamp` to hide drift. Some older downgrades are intentionally unsupported; M9 downgrades delete assessment data. Roll back application code first and retain additive schema where compatible.

## PDF and deployment maintenance

Seven templates render a validated shared context with escaped text. Draft Preview derives a structured representation from rendered LaTeX; React renders known nodes without unsafe HTML injection. It includes unsaved edits. The UI permits PDF downloads only when relevant values match successful saves; the API still accepts a validated snapshot and never persists it. This UI restriction is not a server-enforced saved-version guarantee.

Compiler modes are disabled, local Docker, and native Linux. Production uses native Tectonic 0.15.0 from a pinned resource image, cached packages/fonts, untrusted/offline compilation, temporary directories, timeout and output limits. One worker preserves one compiler at a time. See [Docker/PDF runbook](milestone-9d2c-render-compatibility.md) and [current deployment procedure](production-deployment.md). The default resource image is local-only: a fresh clone cannot build PDFs without the owner handing over the image/archive or approved registry digest. General LaTeX editing, arbitrary templates and PDF compilation services are not supported.

When maintaining AXIOM: preserve snapshot semantics; add focused permission/CSRF tests for mutations; update schemas/clients together; add Alembic revisions for schema changes; test all seven templates after resource/compiler changes; never log document contents, tokens or credentials. Review dependency updates and retain immutable tested image digests. Record the commit, migration revision, test command/result and deployment image for each release.

## Known limits and ownership

No password-reset/MFA workflow, distributed rate limiter, background PDF queue, grade revision history, staff-facing Student Progress dashboard or group-scoped grading. Mathematical input is Unicode, not symbolic validation. Future teaching-tool cards are placeholders. Free-host cold starts, finite memory and request timeouts affect availability. The root health endpoint does not verify PostgreSQL, email or compiler health.

Before accepting maintenance ownership, obtain repository/GHCR/Render/Vercel/Neon/Brevo access through their access controls, artifact references, a tested recovery procedure and agreed data-retention/incident responsibilities. Never transfer these secrets in documentation. See [final handover](final-handover.md).
