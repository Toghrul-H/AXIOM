# Offline resource layer for AXIOM's native Tectonic runtime.
#
# Build context must contain the two reviewed artifacts named below. Neither is
# downloaded during a Docker build. The cache archive is created from a prior,
# reviewed warm-up image; it must contain `.cache/Tectonic` at its root.
ARG DEBIAN_IMAGE=debian:bookworm-slim@sha256:7c7b2c966bc9ee8cedfeef67e0e279108992c77681fa595db4a9d65c06ccc587
FROM ${DEBIAN_IMAGE}

# The official Linux release needs these runtime libraries; certificates are
# required only while a reviewed cache is deliberately warmed.
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates libgraphite2-3 libssl3 \
 && rm -rf /var/lib/apt/lists/*

# Official GitHub release asset: tectonic@0.15.0, x86_64-unknown-linux-gnu.
ARG TECTONIC_ARCHIVE_SHA256=875fbbc9ab48560d7776088c608e0beee49197b57ab4a2f6c5385b2c661c842f
ARG TECTONIC_CACHE_SHA256
COPY tectonic-0.15.0-x86_64-unknown-linux-gnu.tar.gz /tmp/tectonic.tar.gz
COPY tectonic-cache.tar.gz /tmp/tectonic-cache.tar.gz
RUN test -n "$TECTONIC_CACHE_SHA256" \
 && echo "$TECTONIC_ARCHIVE_SHA256  /tmp/tectonic.tar.gz" | sha256sum -c - \
 && echo "$TECTONIC_CACHE_SHA256  /tmp/tectonic-cache.tar.gz" | sha256sum -c - \
 && tar -xzf /tmp/tectonic.tar.gz -C /usr/local/bin \
 && tar -xzf /tmp/tectonic-cache.tar.gz -C /root \
 && test -d /root/.cache/Tectonic \
 && /usr/local/bin/tectonic --version | grep -F 'tectonic 0.15.0' \
 && rm -f /tmp/tectonic.tar.gz /tmp/tectonic-cache.tar.gz

ENV TECTONIC_UNTRUSTED_MODE=1 XDG_CACHE_HOME=/root/.cache
