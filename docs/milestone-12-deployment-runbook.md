# M12 Deployment and Rollback Runbook

This runbook is for a separately authorized production release. It is not a deployment command and contains no credentials. Do not proceed if an item marked **STOP** is not satisfied.

## Preconditions

1. Record the release commit, immutable API-image digest, operator, timestamp, current Render/Vercel deployment references, and rollback revision/image.
2. Confirm a tested Neon recovery point and a restore rehearsal into a separate database. **STOP** if backup scope, retention, or restoration is unverified.
3. Record the actual production database identity and Alembic revision. The repository only has the historical report of `0012`; do not treat it as current fact. **STOP** for an unexpected revision, schema drift, wrong branch, or host.
4. Publish or otherwise provide the exact approved `TECTONIC_RESOURCES_IMAGE` at an immutable registry digest, and build/test the final API image from it. **STOP** if the compiler cache or fonts require runtime downloads, the image cannot be pulled by Render, or the image exceeds service resource limits.
5. Re-run the release quality gates and complete the disposable local browser workflow described in the M12 readiness report.
6. Review Render secrets without displaying them: Neon variables including `DATABASE_SSLMODE=require`; `AUTH_COOKIE_SECURE=true`; exact Vercel URL in `AUTH_ALLOWED_ORIGINS` and `FRONTEND_BASE_URL`; Brevo delivery settings; `PDF_COMPILER_MODE=native`; and demo seeding disabled. Confirm Vercel's server-only `API_BASE_URL` targets the intended Render URL. **STOP** for missing/preview-to-production settings.

## Release sequence

1. Disable automatic promotion/deployment for both services and preserve their current release references and settings.
2. Use an approved external migration runner with the release backend code and private production environment variables. From `backend`, verify then migrate:

   ```text
   python -m alembic current
   python -m alembic heads
   python -m alembic upgrade 0014
   python -m alembic current
   python -m alembic check
   ```

   **STOP** on a target mismatch, unexpected head, permission failure, lock issue, or drift. Never use `stamp` to bypass these checks. Do not place migrations in Docker build or API startup.
3. Deploy the pre-tested backend image to the existing Render service. Retain one worker and the image's normal `$PORT` command. Set Render's health check to `/health`.
4. Verify `GET /health` returns only `{"status":"ok"}` from the intended service. Then perform approved smoke tests: login/session refresh/logout, CSRF rejection, staff/student route separation, registration and Brevo delivery, Question Bank/quiz lifecycle, manual grading, assessment save/reload, each saved-only PDF, and a cold-start request.
5. Deploy/promote the compatible Vercel frontend only after backend smoke tests pass. Verify same-origin proxy authentication, CSRF forwarding, binary PDF download headers, and the browser workflow.
6. Re-enable automation only after documented acceptance by the release owner.

## Verified-question import (separate authorization)

The current importer blocks non-local targets. Keep that control intact. Do not copy the development database.

Before an authorized import, create a reviewed production-only runner/process using the exact release importer and locked source artifacts. It must use least-privileged credentials, take a fresh recovery point, validate the target identity and revision, run read-only dry-runs in order (`m10a3`, `m10c`, `m10e`), verify conflicts and canonical source IDs, then import each batch transactionally. Record created/skipped/conflict/rejected counts and run the idempotency dry-run again. **STOP** for any conflict, rejected record, missing artifact, unknown source ID, or count mismatch. Do not migrate local users, attempts, quiz sessions, or unrelated question records.

## Monitoring and stop conditions

Monitor generic API errors, database readiness, latency/cold starts, memory, PDF timeout/failure categories, and Brevo delivery categories. Do not log passwords, cookies, tokens, recipient addresses, or answer bodies.

Stop or roll back application traffic for: failed database readiness, schema mismatch, repeated 401/403 from the proxy, CSRF failure on normal same-origin requests, failed email delivery, compiler timeout/resource exhaustion, broken PDF download, or unexpected data changes. Escalate any suspected data exposure rather than retrying with weaker controls.

## Rollback and recovery

1. For PDF-only incidents, set `PDF_COMPILER_MODE=disabled` through authorized configuration and redeploy/restart; retain normal application safeguards.
2. For an application failure, restore the recorded compatible frontend and backend image/runtime/settings. Keep additive migrations applied by default: downgrading `0013`/`0014` can drop metadata created after release.
3. A database restore is a separately authorized incident action. Restore only into a verified target, record the recovery point, and assess lost writes before redirecting traffic. Never overwrite production as a rehearsal.
4. For a partial question import, stop further imports, preserve logs/counts, compare canonical IDs, and recover only under the approved import procedure. Do not delete uncertain records manually.

After rollback, document the trigger, affected release, database revision, chosen recovery action, validation outcome, and follow-up owner before another attempt.
