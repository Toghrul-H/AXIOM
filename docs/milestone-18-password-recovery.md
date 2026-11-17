# M18 Password Recovery

M18 adds generic password-reset requests, 30-minute single-use reset tokens,
and an encrypted PostgreSQL delivery outbox. Migration `0026` follows `0025`.

## Required configuration

Configure the existing email provider variables (`EMAIL_DELIVERY_PROVIDER`, the
chosen provider credentials, `EMAIL_FROM_ADDRESS`, `EMAIL_FROM_NAME`, and the
HTTPS `FRONTEND_BASE_URL`) plus:

- `PASSWORD_RESET_OUTBOX_ENCRYPTION_KEY`: one persistent Fernet key. Generate
  it through the `cryptography` package; never put it in source control or
  rotate it while reset work can still be queued.
- `PASSWORD_RESET_OUTBOX_POLL_SECONDS`, `PASSWORD_RESET_OUTBOX_BATCH_SIZE`, and
  `PASSWORD_RESET_OUTBOX_MAX_ATTEMPTS`: bounded worker controls.

The worker sends only after the token and encrypted outbox record commit. It
uses bounded exponential retry and PostgreSQL `SKIP LOCKED` claims. Delivery is
at-least-once: a process crash after a provider accepts a message but before
the acknowledgement commits can produce a duplicate email; every link remains
single-use. Ciphertext is deleted after provider acceptance, retry exhaustion,
or expiry. No plaintext token is stored or logged.
