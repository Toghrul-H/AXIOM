# M9D.2B — Assessment PDF downloads

> Historical implementation record. The subsequent saved-only UX change blocks Download PDF while relevant edits are unsaved; Draft Preview still includes them. Use the [current user guide](user-guide.md) and [production deployment guide](production-deployment.md) for handover procedures. Resource measurements below describe the original local test, not current production state.

The editor's Download PDF action submits the same unsaved form snapshot used by Draft Preview to `POST /assessment-configurations/{id}/documents/{document_type}/pdf`. All seven existing templates remain authoritative and unchanged. This operation does not save configuration records. Lecturer/Admin authorization and session CSRF checks apply. The response is an attachment with `application/pdf` and `Cache-Control: no-store`; the same-origin proxy forwards the binary body and filename.

## Local Windows setup

Start Docker Desktop. The compiler uses the exact warmed M9D.2A Tectonic 0.15.0 image, pinned in `compiler.py` by image ID. If that image is no longer loaded, run from the repository root:

```powershell
& "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe" load -i out/tectonic-poc/pinned-image.tar
```

The archive is a local ignored POC artifact, not a repository dependency download. Preserve it for local reproduction.

Start the backend from the repository root (existing local database/environment setup remains required):

```powershell
cd backend
$env:PDF_COMPILER_MODE='docker'
$env:PDF_DOCKER_EXECUTABLE="$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

In a second terminal, from the repository root:

```powershell
cd frontend
pnpm dev
```

Open http://127.0.0.1:3000 and sign in as Lecturer/Admin. In Assessment Documents, select a document, edit a field that it includes (for example an Endterm room), and click Download PDF without saving. Check the PDF contains the draft value, then switch documents and confirm editor values remain. Reload without saving to confirm the database retains the saved configuration. Repeat download for each of the seven selections. A generating state prevents duplicate requests; failures remain visible without resetting form values.

## Compilation boundaries

Only server-rendered templates reach the compiler; no template path or raw LaTeX is accepted. Existing escaping is retained. Fixed compiler-only macros preserve Hungarian double accents and dashes with the existing font configuration; unsupported glyphs fail explicitly instead of silently disappearing.

Each job uses a unique temporary directory, removed on success or failure. Compilation is offline (`--only-cached`, Docker networking disabled), untrusted, read-only outside its job directory and temporary filesystem, without shell escape. Limits: one concurrent compilation per API process, 30-second default timeout, 1 MB source, 4 MB PDF, 8 MB individual output files, 512 MiB container memory, one CPU, 64 processes. Timeout cleanup also stops the Docker container. Run one API worker. Browser cancellation does not guarantee immediate compiler cancellation; the timeout still bounds the job. Logs expose categories only, not document text.

## Deployment evidence and remaining work

M9D.2A measured a 300,338,650-byte image (about 286 MiB), roughly 167 MiB compiler peak RSS, 0.55–0.87 seconds per document at one CPU, and 8.0–9.5 seconds at 0.1 CPU. The warmed image compiled all seven samples without networking. These are local POC measurements, not Render benchmarks; the API runtime adds memory and image size.

Docker mode is for local Docker Desktop. Render deployment would require a combined API image with the pinned compiler and warmed cache and use `PDF_COMPILER_MODE=native`; the native Linux path uses `prlimit`, a 384 MiB address-space limit, file and CPU limits, and the same wall-clock timeout. That deployment image and native runtime have not been validated here. Do not assume a Docker daemon exists inside Render. Verify total API/compiler memory, cold starts, concurrency, cache permissions and Vercel request-duration limits before production enablement. No runtime package downloads, migrations, new Python/npm dependencies or production changes are part of this milestone.
