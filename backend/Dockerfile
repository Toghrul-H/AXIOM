# Local build: tag the verified M9D.2A image as axiom-tectonic-resources:0.15.0.
# Remote builds MUST override this with a published immutable registry digest.
ARG TECTONIC_RESOURCES_IMAGE=axiom-tectonic-resources:0.15.0@sha256:5b8e4619d122d9584c4b87f20eedf7fc574e8e589342b0cdd521f1d05ffcb6d6
FROM ${TECTONIC_RESOURCES_IMAGE} AS resources

FROM python:3.11-slim-bookworm@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 axiom && useradd --uid 10001 --gid axiom --create-home axiom
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --from=resources /usr/local/bin/tectonic /usr/local/bin/tectonic
COPY --from=resources --chown=10001:10001 /root/.cache/Tectonic /opt/tectonic-cache/Tectonic
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PDF_COMPILER_MODE=native PDF_TECTONIC_EXECUTABLE=/usr/local/bin/tectonic \
    PDF_CACHE_DIRECTORY=/opt/tectonic-cache PDF_TIMEOUT_SECONDS=30 PDF_MAX_BYTES=4000000 \
    TECTONIC_UNTRUSTED_MODE=1
USER 10001:10001
EXPOSE 10000
# No migrations or seeders at startup. One worker preserves the compiler semaphore.
CMD ["sh", "-c", "exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1"]
