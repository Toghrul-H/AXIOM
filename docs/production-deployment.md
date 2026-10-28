# AXIOM Production Deployment and Maintenance

Reviewed against source on 28 October 2026. Hosting below is **owner-reported**, not independently inspected in this task. This guide records procedures for an authorized operator; it does not authorize a deployment. No secret values belong here.

## Architecture and release record

Browser → Vercel Next.js same-origin API proxy → Render FastAPI container → Neon PostgreSQL. Verification email uses Brevo HTTPS. Images are reported as stored in GHCR.

- Reported frontend: https://axiom-orcin-xi.vercel.app/
- Reported backend: https://axiom-api-te6o.onrender.com/
- Source Alembic head: `0012`; owner reports this as the latest verified live revision.
- Before each release, record Git commit, tested image digest, database revision, test evidence, timestamp and operator. The owner must confirm the actual GHCR namespace/package, resource-image digest, live service IDs and current deployment.

## Required configuration

Configure secrets only in the service's secret/environment controls. Process variables override backend `.env`; the Docker build excludes it. The application does not consume a generic `DATABASE_URL` or require an invented JWT signing secret.

| Component            | Variable names / intended values                                                                                                                                                                                                                          |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Neon connection      | `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`; use owner-approved values and migration permissions only for the migration runner                                                                                |
| PostgreSQL transport | Preserve the approved libpq TLS configuration (for example `PGSSLMODE=require` where appropriate); `database_url()` does not add an explicit SSL mode. Confirm the owner's connection/security policy rather than assuming the Docker move configures TLS |
| Session security     | `AUTH_COOKIE_SECURE=true`, `AUTH_ALLOWED_ORIGINS=["https://axiom-orcin-xi.vercel.app"]`, `AUTH_SESSION_HOURS`, `AUTH_REQUESTS_PER_MINUTE`                                                                                                                 |
| Email                | `EMAIL_DELIVERY_PROVIDER=brevo`, `BREVO_API_KEY`, `EMAIL_HTTP_TIMEOUT_SECONDS`, `EMAIL_FROM_ADDRESS`, `EMAIL_FROM_NAME`, `FRONTEND_BASE_URL=https://axiom-orcin-xi.vercel.app`; sender must be verified with Brevo                                        |
| PDF                  | `PDF_COMPILER_MODE=native`, `PDF_TECTONIC_EXECUTABLE=/usr/local/bin/tectonic`, `PDF_CACHE_DIRECTORY=/opt/tectonic-cache`, `PDF_TIMEOUT_SECONDS=30`, `PDF_MAX_BYTES=4000000`                                                                               |
| Server               | Render supplies `PORT`; Docker CMD binds `0.0.0.0` and starts exactly one worker                                                                                                                                                                          |
| Frontend             | Server-side `API_BASE_URL=https://axiom-api-te6o.onrender.com`; never prefix secrets with `NEXT_PUBLIC_`                                                                                                                                                  |
| Local-only controls  | Keep `DEMO_SEED_ENABLED=false`; do not provision production demo passwords or run seed scripts                                                                                                                                                            |

SMTP variables in `backend/.env.example` are an optional local/backward-compatible transport and are unused with Brevo. Do not revert production to SMTP as a workaround for an HTTPS delivery problem. Session cookies remain HttpOnly/SameSite=Lax; the same-origin proxy forwards cookies/CSRF, so browser-to-backend cross-origin authentication is unnecessary.

## Build and publish to GHCR

The Dockerfile pins Python and copies Tectonic 0.15.0 plus warmed fonts/packages from `TECTONIC_RESOURCES_IMAGE`. Its default refers to a **local POC image**, not a publicly available registry artifact. The owner must provide an accessible immutable resource-image reference or the original archived image. Without it, a fresh clone cannot build the PDF image. Do not replace it with an arbitrary compiler tag.

The following PowerShell commands run from the repository root **only for an approved release**. Enter non-secret identifiers at prompts; replace nothing with credentials in source. Use a classic GHCR token with the required package permissions at Docker's hidden password prompt, or an approved secret-injected CI identity. Private pulls require package access; Render needs its own approved read credential. See [GitHub's registry authentication and digest guidance](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

```powershell
$ghcrUser = Read-Host 'Authorized GitHub username'
$resourceImage = Read-Host 'Approved Tectonic resource image, including @sha256 digest'
$apiPackage = Read-Host 'Approved lower-case GHCR package (ghcr.io/owner/package)'
$releaseTag = git rev-parse --short=12 HEAD
$releaseImage = "${apiPackage}:${releaseTag}"
docker login ghcr.io --username $ghcrUser
docker build --platform linux/amd64 --build-arg "TECTONIC_RESOURCES_IMAGE=$resourceImage" -t $releaseImage backend
if ($LASTEXITCODE -ne 0) { throw 'Image build failed' }
# Stop here until this exact image has passed the release checks.
```

After approval of the image checks:

```powershell
docker push $releaseImage
if ($LASTEXITCODE -ne 0) { throw 'Image publication failed' }
docker image inspect $releaseImage --format '{{json .RepoDigests}}'
```

Record and deploy the returned registry digest, not a moving `latest` tag or a local image ID. Commands are parameterized because the actual package/digest has not been verified. Publishing was not performed during this handover. The previous local image test is documented in [M9D.2C](milestone-9d2c-render-compatibility.md); a rebuilt image needs its own verification because OS/transitive Python dependencies are not fully locked.

## Render and Vercel configuration

Prefer deploying the tested prebuilt GHCR image to the existing Render service, retaining its hostname. Render supports changing source/runtime under Settings → Build → Source → Edit. Record current settings before changing them, review environment/health settings, supply private-registry access if necessary and remove any obsolete start-command override. The image CMD starts Uvicorn on `$PORT`, with no seeding or migrations. Health path `/` verifies process availability only. A Git/Dockerfile build instead needs backend as build context and an approved resource-image build argument. See [Render Docker](https://render.com/docs/docker).

Vercel uses the `frontend` project root, Next.js framework, the lockfile/package-manager version, `pnpm install --frozen-lockfile` and `pnpm build`. This is not a static export. Set the server-side API base for each intended environment; preview deployments should not silently use production data. Verify the effective Node runtime and function duration in the owner's project. The PDF route has no explicit `maxDuration`; its allowance must cover backend cold start plus compilation. Keep same-origin handlers/rewrites and the existing binary response flow.

## Safe release order and migrations

1. Hold automatic production deployments on both providers before publishing source. Record rollback commits/images/settings and verify backup recoverability.
2. Run local checks against a disposable local database. Publish the approved source and tested image without triggering a frontend/backend race.
3. Use a separately authorized environment with the release's backend code and privately supplied production database settings. Confirm host/database identity without printing passwords, select the correct Neon branch and check existing revision/schema.
4. Only after backup review and authorization, apply the intended revision:

   ```text
   python -m alembic current
   python -m alembic heads
   python -m alembic upgrade 0012
   python -m alembic current
   python -m alembic check
   ```

   These commands are run from `backend` (or `/app` in the image). Use the release-specific target for future revisions. Stop on unexpected revision, conflict or drift; never use `stamp` to bypass it. Alembic uses configured database variables, not a command-line credential.

5. Deploy backend, verify it, then deploy/promote the compatible frontend. Re-enable automatic deployment only after acceptance.

Migration order is `0009 → 0010 → 0011 → 0012`. 0010 creates assessment tables; 0011 adds nullable writing times; 0012 adds nullable policies/submission fields and new related tables. Existing user/question/quiz/attempt data is not rewritten. DDL still requires privileges and locks. No M9 tables or historical document values are seeded automatically.

Render Free does not provide the paid pre-deploy migration command or interactive shell. Use an approved external runner; do not move migrations into Docker build or silently add them to startup. See [Render deploy commands](https://render.com/docs/deploys). Never run the integration suite against Neon/production.

## Acceptance and troubleshooting

After an authorized rollout, check `/`, then real database-backed behavior: login/logout/session refresh, Student verification email, RBAC and CSRF rejection, Question Bank/quiz operations, Student submission/review, manual grading, assessment save/reload, all seven saved-only PDF downloads and a cold-start request. Use approved test accounts/data and remove only agreed fixtures. Do not treat a green root health check as database or email verification.

| Symptom                        | Checks                                                                                                                      |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------- |
| Image fails to build/pull      | Resource image availability, immutable digest, architecture, GHCR package read permissions and build context                |
| Database 503 / undefined table | Database target, TLS, privileges and revision; never reset the database                                                     |
| Authentication 401/403         | Same-origin proxy, cookie Secure setting, session expiry, role and CSRF/origin forwarding                                   |
| Registration 503               | Sanitized Brevo failure category/status, sender verification and privately configured key; never log tokens or email bodies |
| PDF unavailable                | Native mode and compiler/cache paths; one worker; do not attempt Docker-in-Docker                                           |
| PDF timeout / missing glyph    | Logs' safe failure category, document size/characters, warmed resources and resource contention                             |
| Proxy timeout after idle       | Render wake-up plus Vercel function duration; retry once warm and assess hosting limits                                     |

Compilation runs offline with isolated temporary directories, timeout, size and concurrency limits. API networking is still needed for Neon and Brevo. Free instances sleep after inactivity, may restart and have ephemeral filesystems; do not use local container storage as a backup or student-upload store. [Render Free limitations](https://render.com/docs/free)

## Backup, recovery and maintenance

The owner must agree retention, recovery point/time objectives, encryption, access and an off-provider backup policy. Confirm Neon branch identity and actual restore-window settings: retention is plan/configuration-dependent, not guaranteed by this repository. Rehearse restore into a separate isolated database before relying on a backup; check revision, representative records and application behavior there. Never rehearse by overwriting production. See [Neon backup/restore documentation](https://neon.com/docs/introduction/backup-restore).

For PDF-only incidents, disable PDF mode temporarily. For application rollback, restore a compatible frontend followed by the recorded backend image/runtime/settings. Leave additive M9 schema applied when rolling back pre-M9 application code; M9 downgrades drop data. Keep newer migration tooling available because an old checkout cannot resolve revision 0012. Database restore is a separately approved incident action that may lose writes after the restore point.

Maintain immutable image references, release logs, backup evidence and operator contacts. Review dependencies, certificate behavior and provider limits regularly. Monitor memory, latency, generic error categories and email delivery; do not log secrets or student answer contents. Process-local authentication rate limiting and one-at-a-time PDF compilation are limitations, not an availability guarantee.

## Owner confirmation before operational handover

Confirm current deployment/image/resource digests, GHCR permissions, production schema and database TLS, Vercel timeout, verified Brevo sender, backup/restore evidence, billing/incident owners and data retention. Historical 242-test evidence is owner-reported; it is not a live-service acceptance test. See [final handover](final-handover.md).
