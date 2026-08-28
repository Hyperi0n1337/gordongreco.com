from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from portal_core.errors import ScannerUnavailable


class LibmagicDetector:
    def __init__(self, command: str = "/usr/bin/file") -> None:
        self.command = command

    def mime_type(self, data: bytes) -> str:
        try:
            import magic

            value = magic.from_buffer(data, mime=True)
            if value:
                return str(value)
        except ImportError:
            pass
        executable = shutil.which(self.command) if not os.path.isabs(self.command) else self.command
        if not executable or not Path(executable).is_file():
            raise ScannerUnavailable("neither python-magic nor file(1)/libmagic is available")
        result = subprocess.run(
            [executable, "--brief", "--mime-type", "-"],
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            check=False,
        )
        if result.returncode != 0:
            raise ScannerUnavailable(f"libmagic command failed: {result.stderr.decode(errors='replace')[:200]}")
        return result.stdout.decode("ascii", errors="replace").strip()


class ClamAvScanner:
    def __init__(self, command: str = "/usr/bin/clamdscan") -> None:
        self.command = command

    def scan(self, data: bytes) -> str:
        executable = shutil.which(self.command) if not os.path.isabs(self.command) else self.command
        if not executable or not Path(executable).is_file():
            raise ScannerUnavailable("ClamAV command is unavailable")
        with tempfile.TemporaryDirectory(prefix="gg-scan-") as temp_dir:
            path = Path(temp_dir) / "object.bin"
            path.write_bytes(data)
            os.chmod(path, 0o600)
            args = [executable, "--no-summary"]
            if Path(executable).name == "clamdscan":
                args.append("--fdpass")
            args.append(str(path))
            result = subprocess.run(args, capture_output=True, timeout=120, check=False, text=True)
        if result.returncode == 0:
            return "clean"
        if result.returncode == 1:
            return (result.stdout or result.stderr or "infected").strip()[:500]
        raise ScannerUnavailable(f"ClamAV error {result.returncode}: {(result.stderr or result.stdout)[:300]}")


class QpdfValidator:
    def __init__(self, command: str = "/usr/bin/qpdf") -> None:
        self.command = command

    def validate(self, data: bytes) -> str:
        executable = shutil.which(self.command) if not os.path.isabs(self.command) else self.command
        if not executable or not Path(executable).is_file():
            raise ScannerUnavailable("qpdf command is unavailable")
        with tempfile.TemporaryDirectory(prefix="gg-qpdf-") as temp_dir:
            path = Path(temp_dir) / "object.pdf"
            path.write_bytes(data)
            os.chmod(path, 0o600)
            check = subprocess.run(
                [executable, "--check", str(path)],
                capture_output=True,
                timeout=60,
                check=False,
                text=True,
            )
            if check.returncode not in {0, 3}:  # qpdf 3 means warnings; fail closed below.
                raise ScannerUnavailable(f"qpdf check failed: {(check.stderr or check.stdout)[:300]}")
            if check.returncode == 3:
                raise ScannerUnavailable(f"qpdf warnings are fail-closed: {(check.stderr or check.stdout)[:300]}")
            pages = subprocess.run(
                [executable, "--show-npages", str(path)],
                capture_output=True,
                timeout=30,
                check=False,
                text=True,
            )
            if pages.returncode != 0 or not pages.stdout.strip().isdigit():
                raise ScannerUnavailable("qpdf could not determine page count")
            page_count = int(pages.stdout.strip())
            if page_count < 1 or page_count > 2_000:
                raise ValueError("PDF page count outside policy")
            return f"qpdf structural check passed; pages={page_count}"
