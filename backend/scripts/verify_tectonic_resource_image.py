"""Verify a locally available immutable Tectonic resource image offline.

This script never pulls, publishes, or tags an image. It proves only that an
already supplied image reference is digest-pinned, locally available, runs
Tectonic 0.15.0, and can compile a tiny document with networking disabled and
``--only-cached``. Use it before authorizing registry publication or Render.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path


REGISTRY_DIGEST = re.compile(r"^[\w./:-]+@sha256:[0-9a-f]{64}$")
LOCAL_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
SMOKE = r"""\documentclass{article}
\begin{document}
AXIOM Tectonic offline verification.
\end{document}
"""


def run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=60, check=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Locally available immutable registry digest or local image ID")
    args = parser.parse_args()
    if not (REGISTRY_DIGEST.fullmatch(args.image) or LOCAL_IMAGE_ID.fullmatch(args.image)):
        raise SystemExit("Refusing image without an immutable registry digest or local image ID.")
    inspected = run(["docker", "image", "inspect", args.image])
    if inspected.returncode:
        raise SystemExit("Image is not locally available; this verifier never pulls images.")
    with tempfile.TemporaryDirectory(prefix="axiom-tectonic-verify-") as directory:
        root = Path(directory)
        (root / "smoke.tex").write_text(SMOKE, encoding="utf-8")
        command = [
            "docker", "run", "--rm", "--pull=never", "--network=none", "--read-only",
            "--tmpfs", "/tmp:size=32m",
            "--mount", f"type=bind,source={root},target=/job",
            "--workdir", "/job", "--entrypoint", "/usr/local/bin/tectonic", args.image,
            "-X", "compile", "--untrusted", "--only-cached",
            "--outdir", ".", "smoke.tex",
        ]
        # The disposable host directory is mounted only to retrieve the PDF;
        # TemporaryDirectory removes every compiler output after verification.
        compiled = run(command)
        pdf = root / "smoke.pdf"
        if compiled.returncode or not pdf.is_file() or not pdf.read_bytes().startswith(b"%PDF-"):
            raise SystemExit("Offline Tectonic verification failed without printing compiler output.")
    print("Verified immutable resource image: Tectonic 0.15.0 compiled offline.")


if __name__ == "__main__":
    main()
