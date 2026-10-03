# M8B — Gmail SMTP verification delivery

The existing injectable verification-delivery callable now uses Python's standard
library SMTP adapter. Gmail authenticated STARTTLS uses port 587; disabling
STARTTLS selects implicit TLS on port 465, never plaintext authentication.
Certificate verification and a bounded connection timeout are enabled. Mail is
plain-text UTF-8, with a configured From name/address and a one-hour verification
link: `FRONTEND_BASE_URL/verify-email?token=...`. Tokens and SMTP errors are not
logged or returned to clients. Automated tests mock both SMTP transports globally.

## Configuration

Set these privately in backend environment configuration:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD` (Google App Password, stored as SecretStr)
- `SMTP_USE_TLS`
- `SMTP_TIMEOUT_SECONDS` (optional, defaults to 10)
- `EMAIL_FROM_ADDRESS`
- `EMAIL_FROM_NAME`
- `FRONTEND_BASE_URL`

Use an authorized sender matching the Gmail account or its configured sending
alias. Production requires an HTTPS frontend origin; local HTTP origins are
allowed. The backend environment file remains ignored. No secrets belong in Git.

## Transactions and failures

Registration inserts the unverified STUDENT and hashed token, sends mail, then
commits. SMTP failure rolls back the account/token and returns generic 503; retry
registration later. Resend keeps the existing cooldown/rate limits and replaces
the token transactionally. SMTP failure rolls back that replacement, preserving
the old token and allowing retry; the same generic 202 is returned for all emails
to avoid revealing account existence through delivery failures.

SMTP and PostgreSQL cannot commit atomically: if SMTP accepts a message but the
database commit fails (or SMTP acknowledgement is lost), the received link may be
unusable. Retry registration/resend as appropriate. No account is verified merely
by sending mail. Durable delivery/retries would require a future queue/outbox;
this milestone intentionally uses synchronous bounded SMTP. Rate limiting retains
the existing process-local limitation. No new database migration is needed.

## One manual local smoke test (not run automatically)

1. Confirm the backend uses local PostgreSQL at 0009 and privately configure the
   SMTP settings above. Start the local backend normally.
2. Open its local Swagger `/docs`, select `POST /auth/register`, and submit a new
   **real mailbox you control at @inf.elte.hu**, plus a new password entered only
   locally. Execute once. Do not use another person's mailbox.
3. Expect 201 and one email titled “Verify your AXIOM account”. Do not paste the
   link/token into chat, logs or screenshots. No SMTP credentials are API inputs.
4. Until M8C exists, the browser link target is unfinished. To complete the smoke
   test, privately copy the token into local Swagger `POST /auth/verify-email`;
   expect 204, then sign in normally. Avoid repeated registration/email attempts.

M8C must implement the `/verify-email` page and registration/login/resend UX,
including safe token handling. Production must configure credentials and sender,
confirm outbound SMTP availability, apply the existing 0008/0009 migrations in a
separate deployment, and complete M8C before advertising usable registration.
No real email, deployment or Neon operation is performed by this milestone.
