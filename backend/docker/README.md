# Tectonic resource image inputs

`tectonic-resources.Dockerfile` creates the immutable resource layer consumed
by `backend/Dockerfile`. It deliberately performs no network download.
It installs only the official Tectonic release's Debian runtime libraries
(`libgraphite2-3` and `libssl3`) before validating the compiler.

An authorized release operator must provide a clean, reviewed build context
containing:

- `tectonic-0.15.0-x86_64-unknown-linux-gnu.tar.gz` with SHA-256
  `875fbbc9ab48560d7776088c608e0beee49197b57ab4a2f6c5385b2c661c842f`
  (the official `tectonic@0.15.0` GitHub release asset);
- `tectonic-cache.tar.gz`, extracted from the reviewed warm-up image and
  containing `.cache/Tectonic`, with a recorded SHA-256.

Warm a fresh cache by compiling all seven *rendered* AXIOM templates with
network access in an otherwise disposable container, then archive `/root/.cache`
so that the archive root is `.cache/Tectonic`. Verify every rendered template
again with `--network=none --only-cached` before using that archive. The local
M12A verification archive SHA-256 is
`5a766e9d064afbff228b55a5a1c5f1849218dcf4d254b00d5964dcdf5381b02e`.

Build without using mutable image tags:

```text
docker build --pull=false --build-arg TECTONIC_CACHE_SHA256=<recorded-cache-sha256> \
  -f backend/docker/tectonic-resources.Dockerfile -t <approved-registry>/axiom-tectonic-resources:0.15.0 backend/docker-resource-context
```

Before publication, tag the resulting image with its registry digest and run:

```text
python backend/scripts/verify_tectonic_resource_image.py --image <registry>/<image>@sha256:<digest>
```

The verifier neither pulls nor publishes. The digest must then be supplied to
every API image build; `backend/Dockerfile` intentionally has no fallback:

```text
docker build --platform linux/amd64 --build-arg TECTONIC_RESOURCES_IMAGE=<approved-registry>/axiom-tectonic-resources@sha256:<digest> -t axiom-api:<release> backend
```

The resource layer retains the reviewed archive layout at
`/root/.cache/Tectonic`; the API image copies it into its non-root runtime path
`/opt/tectonic-cache/Tectonic`. The remaining publication, registry
permissions, and Render image configuration require explicit release
authorization. A local image ID is not a registry digest: publish the verified
resource layer first, then use its reported `repository@sha256:...` reference
for the API build.
