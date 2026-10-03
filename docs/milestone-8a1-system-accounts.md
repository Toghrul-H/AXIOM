# M8A.1 — Protected/system-managed accounts

`User.is_system_managed` is a non-null boolean defaulting to false. Migration
0009 follows 0008 and leaves every existing account unprotected, preserving all
other fields. No email allowlist or owner address is embedded in application code.

The backend excludes protected users from `/users` before search and pagination.
Role/status changes through Staff Management reject protected targets with the
existing generic 403 response, including direct ID requests and Admin requests.
Protection grants no application privileges: authentication and RBAC continue to
use the actual role, active flag and email verification state. No public schema
exposes a protection toggle. Public registration remains INF-only and STUDENT-only.

## Private deployment-owner commands

From `backend`, with the intended database configured privately:

```powershell
.\.venv\Scripts\python.exe -m app.scripts.system_accounts create-admin
.\.venv\Scripts\python.exe -m app.scripts.system_accounts protect --user-id 123
```

Use the actual selected ID instead of 123. Both commands prompt for the exact
email, print the target database and operation, and require typing `PROTECT`.
Passwords are requested privately with confirmation, never through CLI arguments.

`create-admin` preserves the existing serialized **first-admin-only** bootstrap
rule: it refuses if any Admin exists or the email is already registered. If an
Admin already exists, use `protect` to intentionally protect that account.
`protect` requires matching ID and email, rejects inactive/legacy/passwordless
accounts, preserves role/password, marks the email verified, removes pending
verification tokens and revokes sessions. It can also protect a Student without
elevating their role. Repeating it safely revokes sessions again. All changes are
transactional. There is no UI toggle, public provisioning API or startup hook.

These are trusted shell operations, not substitutes for authorization: restrict
server shell/database credential access to the deployment owner. They intentionally
support non-INF addresses without changing public registration. No accounts are
automatically protected; no production provisioning is performed by this milestone.

Run migration/tests only against local PostgreSQL with the existing fail-closed
test guard. Production 0008/0009 migration deployment remains a separate operation.
No M8B email provider work is included.
