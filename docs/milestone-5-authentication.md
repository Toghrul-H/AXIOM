# Milestone 5 — authentication, users and authorization

This milestone replaces the development role switcher and browser UUID identity.
FastAPI is the authority for authentication, roles and quiz ownership. Next.js
route guards provide the corresponding navigation and access-denied experience.

## Database and migration

Revision `0005`, after the unchanged migrations `0001`–`0004`, adds:

- `users`: integer ID, normalized unique email, nullable password hash, constrained
  role (`STUDENT`, `DEMONSTRATOR`, `LECTURER`, `ADMIN`), active/legacy flags and
  timezone-aware creation/update timestamps. The legacy flag identifies the one
  migration account; real accounts always receive a password hash.
- `auth_sessions`: SHA-256 digest of an opaque random session token as primary
  key, user foreign key, CSRF token, creation and expiry timestamps. User and expiry
  indexes support lookup/revocation/cleanup. The raw authentication token is never
  stored in PostgreSQL.
- `quiz_attempts.user_id`: required, indexed foreign key with `ON DELETE RESTRICT`.
  The former nullable `development_session_id` is retained solely as audit data;
  neither the API nor frontend uses it to identify a user.

Before migration, the local database contained seven questions, two quizzes, four
attempts and 18 answer snapshots. Migration attached all four attempts to
`legacy-attempts@migration.invalid`, marked inactive and legacy, with no password.
This account cannot log in, appear in staff search, or be managed through the API.
New registrations inherit none of its history. Existing answers, options, scores,
quiz composition and snapshot topic context are preserved.

There is no startup `create_all` or database reset. Revision 0005 intentionally
refuses downgrade because returning new authenticated attempts to a development
identity would be unsafe. A rollback requires a reviewed pre-migration backup.

## Authentication and sessions

Passwords are hashed with `pwdlib[argon2]` using its recommended Argon2id hasher.
Registration and login accept an email and a 12–128-character password. Email is
trimmed/lowercased and validated with `email-validator`. Public registration
always creates STUDENT; unknown fields, including `role`, are rejected (422).
Duplicate normalized email returns 409. Invalid or inactive login returns a generic
401. Passwords/hashes are absent from response schemas and validation responses
never echo submitted input. SQLAlchemy hides statement parameters.

Login creates a 256-bit random opaque token in an HttpOnly, SameSite=Lax, path `/`
cookie named `dmi_session`. Sessions have an absolute 12-hour default expiry.
The same-origin Next.js proxy carries the cookie to FastAPI. `/auth/me` restores
the user and CSRF token after refresh. Authentication tokens are never placed in
localStorage or JavaScript. The CSRF token is held only in client memory.

Every protected request loads the session and the current active, non-legacy user
from PostgreSQL. Role/status changes revoke every session for the affected user.
Logout deletes the current session and expires its cookie. Reactivation requires
a new login; old sessions do not become valid again. Frontend expiry is noticed on
API 401, window focus or a 60-second session check. Backend denial is immediate
for subsequent requests, regardless of what an already-open page displays.

Unsafe authenticated requests require the session's `X-CSRF-Token`, compared in
constant time. Unsafe requests reject untrusted Origin values and cross-site Fetch
Metadata. Login/registration require JSON, preventing simple cross-origin form
submissions. No cross-origin CORS access is enabled. API responses use `no-store`
and vary by Cookie. The existing root greeting and OpenAPI remain public.

Opaque database sessions fit the existing single-backend, same-origin application
and allow immediate revocation without JWT signing keys, refresh tokens or a new
identity service. Random tokens use Python's standard `secrets` implementation;
password hashing uses an established library, not custom cryptography.

## Permissions

| Action | Student | Demonstrator | Lecturer | Admin |
| --- | --- | --- | --- | --- |
| Student catalog, take/resume/submit/review own quiz | Yes | No | No | No |
| Another user's attempts or private history | No | No | No | No |
| Question Bank CRUD and answer-check endpoint | No | Yes | Yes | Yes |
| Staff quiz composition/status | No | Yes | Yes | Yes |
| Course metadata | Yes | Yes | Yes | Yes |
| List/search Students and Demonstrators | No | No | Yes | Yes |
| Student ↔ Demonstrator | No | No | Yes | Yes |
| Student/Demonstrator ↔ Lecturer | No | No | No | Yes |
| Deactivate/reactivate Demonstrator | No | No | Yes | Yes |
| Deactivate/reactivate Student or Lecturer | No | No | No | Yes |
| Manage self, legacy account or Admin account | No | No | No | No |
| Create/promote Admin over HTTP | No | No | No | No |

Staff use the shared `/teacher` content tools; a Demonstrator can also use the
existing `/demonstrator` bank route. There is no blanket administrator bypass for
student attempts. A former Student's attempts remain owned by that account during
a staff role assignment; returning the account to Student restores access to its
own history. No manual grading or staff access to private student work is added.

The management workflow is **register first, then promote**. An Admin promotes an
existing Student/Demonstrator to Lecturer. A Lecturer or Admin can promote a Student
to Demonstrator. Status changes deactivate rather than delete accounts, preserving
relationships. The server explicitly checks allowed transitions, locks the actor
and target, denies self/admin/legacy management, and revokes affected sessions.
The UI confirms role and status changes. There is no generic user-update endpoint.

All attempt reads and writes filter by both attempt UUID and authenticated user ID,
including answer save, final submit and review. Foreign attempts return 404. The
active response allowlist still omits correctness, reference answers, correct-option
flags, explanations and awarded points. Review becomes available after submission;
written answers remain ungraded and snapshot-based.

## Bootstrap the first administrator

From a local PowerShell terminal in `backend/`:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.scripts.create_admin
```

Enter a separate administrator email and a unique password twice at the hidden
password prompts. Do not enter the password into chat, source code, command-line
arguments or documentation. The command normalizes/validates credentials and uses
a PostgreSQL advisory transaction lock to serialize bootstrap. It refuses an
existing email or any existing Admin, including an inactive one. There is no web
bootstrap endpoint. Sign in at `/login`, then use **Staff Management**. Additional
Admin management, password recovery and MFA are outside this milestone.

## API and frontend

| Endpoint | Access / result |
| --- | --- |
| `POST /auth/register` | Public; Student only, 201 |
| `POST /auth/login` | Public; sets cookie, returns user and CSRF token |
| `GET /auth/me` | Current authenticated user and CSRF token |
| `POST /auth/logout` | Current user + CSRF; revokes session, 204 |
| `GET /users?q=&offset=0&limit=20` | Lecturer/Admin; permitted roles only |
| `POST /users/{id}/role` | Lecturer/Admin; explicit allowed transition |
| `POST /users/{id}/status` | Lecturer/Admin; strict boolean `is_active` |
| `/questions` and `/questions/{id}` | Existing staff CRUD, now protected |
| `POST /questions/{id}/check` | Staff only, including solution access |
| `GET/POST /quizzes`, `GET/PUT /quizzes/{id}` | Staff only |
| `GET /student/quizzes` | Student only |
| `POST /student/quizzes/{id}/attempts` | Student only; ownership assigned server-side |
| `GET /student/attempts` | Current Student's history only |
| `GET /student/attempts/{id}` | Current Student's attempt only |
| `PUT /student/attempts/{id}/answers/{item_id}` | Owner + CSRF |
| `POST /student/attempts/{id}/submit` | Owner + CSRF |
| `GET /student/attempts/{id}/review` | Owner; submitted attempts only |

Frontend `/login`, `/register` and `/teacher/users` are new. Registration has no
role selector. The authenticated shell derives navigation from the real user and
replaces the development role switcher with email, role and Sign out. Guards block
unauthenticated or wrong-role page content; FastAPI independently enforces access.
`src/lib/auth.ts` supplies cookies/CSRF for the existing question and quiz clients.
The Next.js proxy now includes `/api/auth/*` and `/api/users/*`.

Swagger remains at `http://127.0.0.1:8000/docs`. Login there first to set its host
cookie, then copy the response's `csrf_token` into the documented `X-CSRF-Token`
header for protected mutations. Use the same hostname consistently. Swagger cannot
override HttpOnly cookies manually; login supplies them. Avoid sharing screenshots
or logs containing login responses or CSRF tokens.

## Configuration, dependencies and startup

Backend `.env.example` adds these safe settings; existing `.env` is never overwritten:

| Variable | Local default |
| --- | --- |
| `AUTH_COOKIE_SECURE` | `false` for local HTTP; **true for HTTPS** |
| `AUTH_SESSION_HOURS` | `12` (1–168) |
| `AUTH_REQUESTS_PER_MINUTE` | `30` (1–1000) |
| `AUTH_ALLOWED_ORIGINS` | JSON list of localhost/127.0.0.1 on ports 3000 and 8000 |

`DATABASE_PASSWORD` remains local/private. No JWT signing secret is needed for this
architecture: session secrets are generated server-side at login. Never put any
database or authentication secret into a `NEXT_PUBLIC_*` variable. The frontend
still needs only server-side `API_BASE_URL=http://127.0.0.1:8000`.

New direct dependencies: `pwdlib[argon2]==0.3.0`, `email-validator==2.3.0`.
Argon2 CFFI/bindings and DNS validation dependencies are installed transitively.
No frontend dependency was added.

Startup remains:

```powershell
# backend/
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
# frontend/ in a second terminal
pnpm dev
```

## Boundaries and production follow-up

- This is a local-development milestone. Production needs HTTPS, Secure cookies,
  an exact HTTPS origin allowlist, secure proxy configuration, backups, secret
  management and appropriate security headers. Do not expose the current dev servers.
- The in-process IP limiter protects login/registration locally. Multiple workers
  need a shared limiter; behind Next.js, clients may share the proxy address. Design
  trusted proxy handling and deployment-level abuse controls before release.
- Session expiry is checked on every request; expired rows are cleaned during
  login. High-volume deployment should schedule cleanup and consider session caps.
- No verified-email identity, password-reset flow, MFA, security audit trail, remote
  Admin recovery or comprehensive identity platform is claimed. Those are deferred.
- Frontend guarding is UX, not a security boundary. Already-rendered data cannot be
  recalled from a browser after revocation. New backend requests are denied.
- Backend tests still produce the two existing Starlette/httpx and AnyIO deprecation
  warnings. See the verification record for exact counts and commands.

Implementation guidance: [FastAPI password hashing](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/),
[OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html),
and [OWASP CSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).
