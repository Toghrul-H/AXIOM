# Disposable, network-enabled cache warm-up only. It is never used at runtime.
ARG TECTONIC_RESOURCES_IMAGE
FROM ${TECTONIC_RESOURCES_IMAGE}

# XeTeX needs Fontconfig when producing the cached Computer Modern math fonts.
RUN apt-get update && apt-get install -y --no-install-recommends fontconfig \
 && rm -rf /var/lib/apt/lists/*

COPY tectonic-cache-warmup.tex /work/tectonic-cache-warmup.tex
# Deliberately omit --only-cached here: this is the controlled one-time warm-up.
RUN /usr/local/bin/tectonic -X compile --untrusted --keep-logs \
 --outdir /work /work/tectonic-cache-warmup.tex \
 && test -s /work/tectonic-cache-warmup.pdf \
 && rm -f /work/tectonic-cache-warmup.{aux,log,xdv,pdf}
