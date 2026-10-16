# M9D.2C — Render Free compatibility

Verified locally on 2026-10-15, starting from `8203d82`. No production access, deployment, database connection, migration execution, commit or push occurred.

## Result

Conditional GO for a supervised, low-traffic deployment after the preparation gates below. All seven representative documents compile offline in the proposed FastAPI image with 512 MiB RAM, no swap and 0.1 CPU. This is not a production reliability or concurrent-user guarantee. Render itself advises against Free instances for production applications.

| Local measurement | Result |
| --- | --- |
| Image size reported by Docker | 460,281,580 bytes (439 MiB; not registry transfer size) |
| Peak entire container memory, including page cache | 276,606,976 bytes (264 MiB) |
| API + test driver baseline memory | 108,265,472 bytes (103 MiB) |
| Compiler maximum RSS | 170,604 KiB (167 MiB) |
| API startup at 0.1 CPU | 14.0 seconds |
| Compilation per document at 0.1 CPU | 7.497–8.104 seconds |
| Concurrent API root probes | 99 successful; maximum latency 1.084 seconds |
| OOM events / leftover job directories | 0 / 0 |

The probe runs the real Uvicorn app plus an extra Python driver invoking the production `compile_pdf` service in the same container. Thus the total includes extra driver overhead, but excludes real database queries, sessions, password hashing, email delivery and production traffic. The API root is exercised during compilation; authenticated PDF endpoints were already covered in M9D.2B, not re-tested against a database here. These samples are not worst-case document-size or concurrency tests.

All seven passed: Dates of Assessments, Endterm, Rules of Assessment, Plus Points Rules, Midterm, Retake, Coursework. Local outputs and raw measurements are in ignored `out/m9d2c/`; `verify.py` there reproduces the measurement. Native compilation uses the existing Unicode handling and unsupported-glyph checks. No template changes were needed.

## Image design

`backend/Dockerfile` uses pinned Python 3.11/bookworm and copies only Tectonic 0.15.0 and its complete warmed resource cache from the pinned M9D.2A image. The cache contains the required packages, fonts and format resources. The POC's PDFs, sources and Poppler tooling are not copied. Runtime additions are CA certificates and `util-linux` for `prlimit`, plus the existing backend requirements.

The application runs as UID 10001, one Uvicorn worker, listening on `0.0.0.0:$PORT` (10000 fallback). `PDF_COMPILER_MODE=native` executes the compiler directly; no Docker client, socket or nested containers are needed. Runtime compilation is `--untrusted --only-cached`. The test also disabled all container networking and made its root filesystem read-only, with only `/tmp` and the output bind mount writable. Render still needs normal networking for PostgreSQL and Brevo; do not disable service networking there.

Existing 30-second wall timeout, 384 MiB compiler address-space limit, CPU/file/PDF bounds, single-compiler semaphore and cleanup are retained. One worker is essential because the semaphore is process-local. Startup does not install packages, download LaTeX resources, migrate or seed accounts.

`backend/.dockerignore` allowlists application/migration sources and requirements, excluding local environments, credentials and generated caches. No secrets are baked into the image. OS packages and transitive Python dependencies are not fully locked; deploy the tested final image by immutable registry digest to avoid rebuild drift.

## Local reproduction

From the repository root in PowerShell, with Docker Desktop running:

```powershell
$docker = "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe"
# Only if the original image has been removed:
# & $docker load -i out/tectonic-poc/pinned-image.tar
& $docker tag sha256:5b8e4619d122d9584c4b87f20eedf7fc574e8e589342b0cdd521f1d05ffcb6d6 axiom-tectonic-resources:0.15.0
& $docker build --platform linux/amd64 -t axiom-api:m9d2c backend
$samples = (Resolve-Path out/tectonic-poc/source).Path
$results = (Resolve-Path out/m9d2c).Path
& $docker run --rm --network none --memory 512m --memory-swap 512m --cpus 0.1 --pids-limit 64 --cap-drop ALL --security-opt no-new-privileges --read-only --tmpfs /tmp:size=64m -e PYTHONPATH=/app --mount "type=bind,source=$samples,target=/samples,readonly" --mount "type=bind,source=$results,target=/results" axiom-api:m9d2c python /results/verify.py
```

The resource image reference is local, not available to Render. A Git-based remote build needs that image published to an approved registry and `TECTONIC_RESOURCES_IMAGE` overridden with its registry digest. Preferred first deployment: publish the already-tested final API image instead, and deploy that immutable digest. Nothing has been published.

## Later deployment procedure — requires separate approval

1. Record the existing Render service source/runtime, deployed revision, build/start commands, root directory, health path and environment-variable names securely. Preserve actual secret values only in existing secret storage. Preserve the current frontend deployment as a rollback target. Confirm existing schema compatibility: this milestone adds no migration, but production may still lack earlier M9 migrations.
2. After explicit publication approval, tag and publish the tested final image to an approved container registry. Record its registry digest; a local image ID is not a remotely pullable reference. If rebuilding instead, first publish the exact resource image, configure its immutable digest, and repeat this image check before promotion.
3. Confirm Vercel's actual function duration setting and Fluid Compute status. The assessment proxy currently defines no `maxDuration`. Allow at least 120 seconds for cold startup plus compilation; Fluid Compute Hobby currently defaults to 300 seconds. Legacy/default overrides may be shorter. Do not change the same-origin cookie/CSRF proxy architecture.
4. Confirm a recoverable database backup and an approved migration plan. In a separately authorized trusted environment, inspect `alembic current` and `alembic heads` before any needed `alembic upgrade head`. Do not put migrations in Docker build steps. Free services lack paid pre-deploy commands and shell access; the image intentionally does not migrate on startup. No migration was run in this task.
5. In the existing Render service, Settings → Build → Source → Edit, select the approved prebuilt image by registry digest and its registry credentials if private. Retain the existing service/hostname and environment settings. Clear any old Python build/start command override so the image CMD runs; set health check `/`. Render supports changing runtime/source, but actual service configuration has not been inspected. Review all settings before confirming the deploy action.
6. Verify these non-secret PDF settings: `PDF_COMPILER_MODE=native`, `PDF_TECTONIC_EXECUTABLE=/usr/local/bin/tectonic`, `PDF_CACHE_DIRECTORY=/opt/tectonic-cache`, `PDF_TIMEOUT_SECONDS=30`, `PDF_MAX_BYTES=4000000`. These defaults are in the image; remove/replace any existing `docker` mode override. Retain all existing database/TLS, secure-cookie/origin, Brevo and frontend URL settings. Keep demo seeding disabled. Render supplies `PORT`. Keep one worker.
7. If the service hostname is retained, Vercel's server-only `API_BASE_URL` does not change. After deployment approval and rollout, verify readiness, login, permissions, saved-only downloads for all seven selections, one cold-start request and peak memory under representative use. Do not declare success based solely on `/`, which does not test database readiness. Avoid concurrent authentication bursts while initially measuring headroom.

For a Git/Dockerfile deployment alternative, use backend root/build context, `Dockerfile` within that root, and a published resource digest as the build argument; retain the same CMD and runtime environment. The current local resource reference cannot be used unmodified on Render.

## Rollback and limits

First mitigation: set `PDF_COMPILER_MODE=disabled` and restart/redeploy, preserving the rest of AXIOM. For a broader failure, restore the recorded previous source/runtime and exact deployed revision (or previous immutable image). Free retains only the two most recent prior deploys; retain the rollback reference separately and do not assume automatic rollback restores source/environment settings. Keep additive schema changes; do not automatically downgrade migrations. If the frontend release depends on new backend endpoints, restore its compatible previous deployment too.

Remaining risks: Free sleeps after 15 minutes and wake-up can take about a minute; it can restart unexpectedly. The local 14-second startup is not Render's complete cold-start time. Password hashing and concurrent requests can consume the roughly 248 MiB measured headroom; a 384 MiB compiler address-space cap does not reserve RAM for the API. Long documents may hit the timeout. Cache misses fail offline. Root probes do not establish Neon/session/email compatibility. Image distribution and actual Vercel settings are still deployment gates. For an availability commitment or substantial classroom concurrency, use a paid instance and load-test before acceptance.

Sources checked: [Render Docker](https://render.com/docs/docker), [runtime changes](https://render.com/docs/native-runtimes), [Free limits](https://render.com/docs/free), [compute plans](https://render.com/docs/compute-plans), [pre-deploy limitations](https://render.com/docs/deploys), [Vercel durations](https://vercel.com/docs/functions/configuring-functions/duration).
