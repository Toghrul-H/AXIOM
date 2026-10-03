# M8C — Email verification UX

Registration explains the exact INF domain rule and keeps password confirmation.
Successful registration navigates to `/check-email?registered=1`, without creating
a session. The query flag controls confirmation copy only, never authorization.
The resend form gives identical conditional wording for all accepted requests.
Backend cooldown/rate limits and account-enumeration behavior remain authoritative.

`/verify-email?token=...` reads the token once, removes it from browser history,
and posts it in the JSON body through `/api/auth/verify-email`. It keeps the token
only in component memory for retries. It does not store or log it. Referrer policy
is no-referrer and indexing is disabled. Hosting access logs may still capture the
initial link URL: redact query strings for this route in deployment logging.
React effect replay shares one request rather than consuming a token twice.

Missing/malformed links, success and service failures have separate states. The
backend deliberately groups invalid/expired/used/superseded links; the UI does too.
Success offers Sign In. Other states offer resend, and service failures offer
retry. Already authenticated users can still open verification pages.

Login offers resend only when the backend explicitly returns its unverified-account
403 message. Ordinary login, HttpOnly cookies, CSRF and role navigation remain.
The external auth rewrite is replaced by an explicit allowlisted GET/POST handler
that forwards cookies/CSRF/origin headers, preserves Set-Cookie and Retry-After,
disables caching and refuses upstream redirects. No backend/schema changes.

## One manual local end-to-end test

1. With local PostgreSQL at 0009 and SMTP privately configured, start the backend
   from `backend`: `.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`.
2. From `frontend`, run `pnpm dev`; use `http://127.0.0.1:3000`. Backend
   `FRONTEND_BASE_URL` must match. Keep frontend `API_BASE_URL` pointing locally.
3. Register once with an INF mailbox you control and a private password. Confirm
   the check-email screen; do not share credentials or the received link.
4. Open the SMTP email's link. Confirm “Email verified successfully.”, then sign
   in and confirm Student dashboard access.
5. To test resend before verification, enter the same address on `/check-email`
   after the backend's 60-second cooldown. Confirm generic wording, open only the
   newest email link; the previous link should show the grouped invalid state.

Automated tests use mocked requests; they send no email. Production still needs a
separate reviewed 0008/0009 migration deployment, backend SMTP/sender/frontend URL
configuration, frontend/backend releases and one controlled end-to-end check.
No production environment, Neon database or protected-account policy is changed.
