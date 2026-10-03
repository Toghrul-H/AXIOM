# M8A — INF registration and email verification foundation

Public registration accepts parsed email addresses with exactly `inf.elte.hu` as
the domain (case insensitive). It always creates an unverified STUDENT; extra
role/verification fields are rejected. Existing login and trusted bootstrap/demo
provisioning keep their existing email rules.

## Storage and compatibility

Alembic **0008**, after 0007, adds `users.email_verified` with a true default,
grandfathering existing users without changing sessions, roles, passwords or
history. Trusted provisioning retains this default; public registration explicitly
sets false. `email_verifications` has a user primary/foreign key (cascade delete),
unique SHA-256 token hash, creation timestamp and expiration timestamp.

Tokens use 32 random bytes, expire after one hour, and are deleted on successful
verification. Only hashes are stored. Resends replace the previous token after a
60-second per-account cooldown. User row locks serialize resend/verification;
verification rechecks the token after acquiring the lock. Expired, superseded and
consumed tokens fail. No tokens appear in API responses or logs.

## Endpoints

- `POST /auth/register`: existing email/password payload and 201 user response;
  creates an unverified account and requests verification delivery.
- `POST /auth/verify-email`: JSON `{ "token": "..." }`; 204 on success, 400 for
  unusable tokens, 422 for invalid payloads. Does not create a login session.
- `POST /auth/resend-verification`: JSON `{ "email": "..." }`; generic 202
  response for unknown, verified, inactive and pending accounts. Cooldown does
  not reveal account existence. Registration's existing duplicate 409 remains.

The existing IP rate limiter covers all three endpoints. It is process-local;
a shared limiter remains deployment technical debt. Origin/content-type checks
apply. These unauthenticated flows do not require a session CSRF token; their
verification token is proof of mailbox possession. Existing authenticated CSRF
checks and RBAC are unchanged. Correct-password login for an unverified account
returns 403; existing sessions for unverified users are rejected too.

## Delivery boundary and M8B

`get_verification_delivery` injects a callable receiving the email and raw token
only in memory. M8A's implementation deliberately sends nothing. Tests replace
it with an in-memory collector. **New public users cannot finish verification
through a mailbox until M8B is implemented.** Do not advertise a working email
registration flow yet.

M8B must supply the delivery adapter, provider configuration/secrets, trusted
frontend verification URL, verification/resend UI and delivery-failure handling.
The callable runs before commit: exceptions roll back token/account changes.
If delivery is asynchronous, M8B must handle transactional enqueue/commit and
retries; do not send mail before a transaction commits without handling failures.
Never persist reusable raw tokens or put them in application logs. No provider,
SMTP credentials, production URL or new environment variables are added in M8A.

## Verification

Tests cover schema validation, token lifecycle, cooldown/rate limiting, session
blocking, unchanged RBAC and migration preservation/roundtrip. Integration tests
require `RUN_POSTGRES_TESTS=1` and a loopback PostgreSQL connection; the test suite
refuses non-local hosts before running any test. Migration 0008 must be applied
before running the updated backend. No production migration is run by this work.

Local verification completed against localhost / dmi_platform with the safety
guard enabled. Migration 0008 applied and Alembic reported 0008 (head). All five
existing users were preserved and verified, with passwords, roles and active
flags unchanged. The complete suite ran with PostgreSQL enabled: 128 passed and
one test-only assertion failed because its token `short` matched the validation
label `too_short`. After choosing a distinct invalid test token, all 25 targeted
M8A tests passed. All 129 tests are covered by these runs; no integration tests
remain skipped. Two existing dependency deprecation warnings remain. No Neon
migration or M8B work was performed.
