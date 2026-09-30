# Milestone 5 verification — 2026-09-23

Status: implementation and automated verification complete; staff browser checks
await approval for the temporary administrator fixture. Do not treat this record
as final Milestone 5 sign-off until those rows are completed.

## Automated checks

Using the existing Python 3.11.9 virtual environment and local PostgreSQL 18.6:

```powershell
# backend/
$env:RUN_POSTGRES_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic check
```

- **76 tests passed**, including the complete prior milestone suite.
- Two existing test-framework warnings: Starlette's httpx integration and AnyIO's
  old BlockingPortal alias. No test failures or database fallback.
- `pip check`: no broken requirements.
- Alembic: `0005 (head)`; no new upgrade operations detected.

The suite covers public Student-only registration; all privileged-role injection
attempts; normalized duplicate email; Argon2id verification; valid/invalid/inactive
login; `/auth/me`; logout replay; expired sessions; HttpOnly/SameSite and HTTPS Secure
cookie configuration; CSRF, cross-origin and malformed-header rejection; local
throttling; all four roles against protected endpoints; Lecturer/Admin hierarchy;
immediate revocation on role/status change; reactivation with fresh login; authorized
staff CRUD; and cross-student attempt retrieval, modification, submission and review.

Quiz regression tests retain snapshot immutability, answer hiding, Unicode input,
saved/resumed answers, concurrent idempotent submission, exact-set objective grading,
and ungraded written responses. No authentication dependency is bypassed in these
API tests; they use real database users and revocable sessions.

Additional isolated-schema tests upgrade populated **0004 → 0005** for both active
and completed attempts, compare every pre-existing field of quizzes, attempts,
answer snapshots and option snapshots, and verify non-null ownership plus the
inactive passwordless legacy account. They execute the interactive bootstrap
command with test-only supplied input, verify an active normalized-email Admin and
valid hash, check that no password is printed, and reject a second Admin. Public
tables are untouched; temporary schemas are removed.

Frontend checks, using the locally installed tools corresponding to package scripts:

```powershell
# frontend/
pnpm format:check
pnpm lint
pnpm typecheck
pnpm build
```

All four passed. Production build includes `/login`, `/register`, `/teacher/users`
and the existing question/quiz routes. No frontend dependencies were added.

## Browser verification

Performed through the actual Next.js frontend on `http://127.0.0.1:3000`, proxying
to FastAPI on port 8000. Disposable credentials were generated only in memory and
were neither printed nor embedded in source. No real user's password was requested.

| Check | Result |
| --- | --- |
| Public registration | Passed: UI confirmed Student; PostgreSQL role is STUDENT; no role selector |
| Login/logout/login again | Passed; logout returned to sign-in and backend returned 204 |
| Browser refresh | Passed; correct Student session and navigation restored |
| Student navigation | Dashboard, Learn, Quizzes, Progress; no Question Bank or staff links |
| Direct Question Bank page | Passed: Access denied |
| Direct Question Bank API | Passed: browser navigation to `/api/questions` reached backend `GET /questions` and returned **403**; browser displayed a blocked-response error rather than rendering JSON |
| Quiz catalog | Both original development quizzes visible; new Student history empty |
| Start and own an attempt | Passed; PostgreSQL confirmed user ID 117 owns the browser-created attempt |
| Save/resume/refresh | Passed; objective answers and written response persisted |
| MathAnswerInput | Passed; Relations/Functions toolbar inserted ∀ and it survived resume/refresh |
| Active answer hiding | No correct answer/reference/solution displayed before submission; recursive API allowlist tests also passed |
| Another Student's attempt | Passed: second Student saw “Attempt not found”, backend returned 404 |
| Finish and review | Passed: confirmation, 3/3 objective points, written response ungraded, all four answers/explanations shown |
| Admin bootstrap | Isolated interactive-command tests passed; temporary live Admin fixture pending approval |
| Admin → Lecturer management | API tests passed; browser check pending |
| Lecturer → Demonstrator promotion | API tests passed; browser check pending |
| Demonstrator login/Question Bank/no staff management | API tests passed; browser check pending |
| Deactivation/revocation/reactivation | API tests passed; browser check pending |
| Authorized Question Bank CRUD | All three staff roles passed API CRUD; browser check pending |
| Authorized quiz management | Existing authenticated quiz-management tests passed; browser check pending |

The verified browser attempt was `75b9f516-3e03-4d9c-b252-9ab9fc801cb7` for
`m5-verify-student@example.com`; `m5-verify-peer@example.com` was the second Student.
These are test fixtures, not real student records. Cleanup is pending the remaining
browser tests. The earlier interrupted run also left `m5-browser-student@example.com`.

## Data preservation

Reinspection at the start of this continuation confirmed:

- Question IDs **19–25**, seven total.
- Quizzes **5** and **6**, both ACTIVE: `[DEV] Foundations Quiz` and `[DEV] Mixed DMI Quiz`.
- The four original attempt UUIDs still exist, all owned by migration user 1.
- All **18 original answer snapshots** remain, including the original completed and
  in-progress statuses. No existing attempt was exposed to a new registration.
- Browser testing added one explicitly identified test attempt; it does not replace
  or alter the historical attempts.

Both local environment files remain Git-ignored. No reset, migration rewrite,
production-table startup creation, or Milestone 6 functionality was introduced.

## Approval boundary

Automatic approval review rejected a command that would create the temporary Admin
`m5-verify-admin@example.com` through the bootstrap function and set its password
hash to the disposable browser fixture's hash. The reviewer cited persistent
privileged access and the credential mutation. The command did not run; a read-only
check confirmed there are **zero Admin accounts**. Approval was requested for that
exact fixture and subsequent cleanup; no workaround was used.

See [the operating guide](milestone-5-authentication.md) for architecture, endpoints,
bootstrap instructions, configuration and security limitations.
