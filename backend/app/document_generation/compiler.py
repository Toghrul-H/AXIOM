"""Bounded compilation of server-rendered templates; never an arbitrary TeX API."""
import logging
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from threading import BoundedSemaphore
from uuid import uuid4

from fastapi import HTTPException
from app.config import get_settings

log = logging.getLogger(__name__)
# One compiler per API process. Deploy exactly one worker (see PDF runbook).
_slot = BoundedSemaphore(1)
PINNED_IMAGE = 'sha256:5b8e4619d122d9584c4b87f20eedf7fc574e8e589342b0cdd521f1d05ffcb6d6'


def compiler_source(source: str) -> str:
    # Tectonic/XeTeX ignores inputenc while these trusted templates select T1.
    # Express equivalent glyphs using fixed TeX macros; wording is unchanged.
    return source.translate(str.maketrans({
        'ő': r'\H{o}', 'Ő': r'\H{O}', 'ű': r'\H{u}', 'Ű': r'\H{U}',
        '–': r'\textendash{}', '—': r'\textemdash{}',
    }))


def compile_pdf(source: str) -> bytes:
    settings = get_settings()
    if settings.pdf_compiler_mode == 'disabled':
        raise HTTPException(503, 'PDF generation is not configured.')
    if len(source.encode('utf-8')) > 1_000_000:
        raise HTTPException(413, 'Document is too large to compile.')
    if not _slot.acquire(blocking=False):
        raise HTTPException(503, 'Another PDF is being generated. Please retry.', headers={'Retry-After': '5'})
    name = 'axiom-pdf-' + uuid4().hex
    env = {k: v for k, v in os.environ.items() if k in {'PATH', 'SystemRoot', 'WINDIR', 'TEMP', 'TMP', 'HOME', 'USERPROFILE', 'LOCALAPPDATA'}}
    env['TECTONIC_UNTRUSTED_MODE'] = '1'
    docker = settings.pdf_compiler_mode == 'docker'
    try:
        with TemporaryDirectory(prefix='axiom-pdf-') as directory:
            root = Path(directory)
            (root / 'document.tex').write_text(compiler_source(source), encoding='utf-8')
            args = ['tectonic', '-X', 'compile', '--untrusted', '--only-cached', '--keep-logs', '--outdir', '.', 'document.tex']
            if docker:
                command = [settings.pdf_docker_executable, 'run', '--rm', '--pull=never', '--name', name,
                           '--network=none', '--memory=512m', '--memory-swap=512m', '--cpus=1', '--pids-limit=64',
                           '--cap-drop=ALL', '--security-opt=no-new-privileges', '--read-only', '--tmpfs', '/tmp:size=32m',
                           '--ulimit', 'fsize=8388608:8388608', '--mount', f'type=bind,source={root},target=/job',
                           '--workdir', '/job', PINNED_IMAGE, *args]
            else:
                # Native Linux deployment uses the exact warmed image resources.
                # prlimit avoids unsafe preexec_fn in FastAPI's threaded workers.
                env['XDG_CACHE_HOME'] = settings.pdf_cache_directory
                command = ['/usr/bin/prlimit', '--as=402653184', '--fsize=8388608', '--cpu=30', '--',
                           settings.pdf_tectonic_executable, *args[1:]]
            try:
                result = subprocess.run(command, cwd=root, env=env, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        timeout=settings.pdf_timeout_seconds, check=False)
            except subprocess.TimeoutExpired:
                log.warning('PDF compilation failed category=timeout')
                raise HTTPException(504, 'PDF generation timed out. Please retry with a shorter document.') from None
            except OSError:
                log.warning('PDF compilation failed category=unavailable')
                raise HTTPException(503, 'PDF compiler is unavailable.') from None
            finally:
                if docker:
                    # Also stop the container if the Docker client timed out.
                    try:
                        subprocess.run([settings.pdf_docker_executable, 'rm', '-f', name], env=env,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
                    except (OSError, subprocess.TimeoutExpired):
                        log.error('PDF container cleanup failed')
            output = root / 'document.pdf'
            if result.returncode != 0 or not output.is_file():
                log.warning('PDF compilation failed category=compiler')
                raise HTTPException(422, 'Could not compile this document. Check its text and retry.')
            if output.stat().st_size > settings.pdf_max_bytes:
                raise HTTPException(413, 'Generated PDF exceeds the download size limit.')
            compiler_log = root / 'document.log'
            if compiler_log.exists() and 'Missing character:' in compiler_log.read_text(encoding='utf-8', errors='replace'):
                raise HTTPException(422, 'The PDF font cannot display a character in this document. Review the text.')
            pdf = output.read_bytes()
            if not pdf.startswith(b'%PDF-'):
                raise HTTPException(502, 'The PDF compiler returned an invalid document.')
            return pdf
    finally:
        _slot.release()
