from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .errors import IntegrityFailure, ScannerUnavailable
from .models import ScanFinding, ScanResult


class MagicDetector(Protocol):
    def mime_type(self, data: bytes) -> str: ...


class MalwareScanner(Protocol):
    def scan(self, data: bytes) -> str: ...


class PdfValidator(Protocol):
    def validate(self, data: bytes) -> str: ...


EXECUTABLE_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"MZ", "PE/Windows executable"),
    (b"\x7fELF", "ELF executable"),
    (b"\xfe\xed\xfa\xce", "Mach-O executable"),
    (b"\xce\xfa\xed\xfe", "Mach-O executable"),
    (b"\xfe\xed\xfa\xcf", "Mach-O executable"),
    (b"\xcf\xfa\xed\xfe", "Mach-O executable"),
    (b"\xca\xfe\xba\xbe", "Mach-O universal/Java class signature"),
    (b"#!", "script/shebang"),
)

EXECUTABLE_MIMES = {
    "application/x-dosexec",
    "application/x-executable",
    "application/x-pie-executable",
    "application/x-sharedlib",
    "application/x-mach-binary",
    "application/x-shellscript",
    "text/x-shellscript",
}

ALLOWED_MIMES = {
    "application/pdf": {".pdf"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "text/plain": {".txt"},
    "text/csv": {".csv"},
    "application/csv": {".csv"},
}

PDF_ACTIVE_MARKERS = (
    b"/JavaScript",
    b"/JS",
    b"/Launch",
    b"/OpenAction",
    b"/EmbeddedFile",
    b"/RichMedia",
    b"/XFA",
    b"/AA",
)


def executable_signature(data: bytes) -> str | None:
    sample = data[:16]
    for signature, label in EXECUTABLE_SIGNATURES:
        if sample.startswith(signature):
            return label
    return None


@dataclass
class ScanPipeline:
    magic: MagicDetector
    malware: MalwareScanner
    pdf: PdfValidator

    def scan(self, *, data: bytes, filename: str) -> ScanResult:
        findings: list[ScanFinding] = []
        if not data:
            raise IntegrityFailure("empty document")

        signature = executable_signature(data)
        findings.append(
            ScanFinding("executable_signature", "fail" if signature else "pass", signature or "none")
        )
        if signature:
            return ScanResult(False, "application/octet-stream", tuple(findings), signature)

        try:
            mime = self.magic.mime_type(data).strip().lower().split(";", 1)[0]
        except Exception as exc:
            raise ScannerUnavailable("libmagic unavailable or failed") from exc
        if not mime:
            raise ScannerUnavailable("libmagic returned no MIME type")
        findings.append(ScanFinding("libmagic", "pass", mime))
        if mime in EXECUTABLE_MIMES:
            return ScanResult(False, mime, tuple(findings), "executable MIME type rejected")

        suffix = Path(filename).suffix.lower()
        allowed_extensions = ALLOWED_MIMES.get(mime)
        if allowed_extensions is None or suffix not in allowed_extensions:
            findings.append(ScanFinding("content_extension_match", "fail", f"{mime} vs {suffix}"))
            return ScanResult(False, mime, tuple(findings), "content type or extension not allowed")
        findings.append(ScanFinding("content_extension_match", "pass", suffix))

        if mime == "application/pdf":
            if not data.startswith(b"%PDF-"):
                findings.append(ScanFinding("pdf_header", "fail", "missing %PDF header"))
                return ScanResult(False, mime, tuple(findings), "invalid PDF header")
            marker = next((item for item in PDF_ACTIVE_MARKERS if item in data), None)
            if marker is not None:
                findings.append(
                    ScanFinding("pdf_active_content", "fail", marker.decode("ascii", errors="replace"))
                )
                return ScanResult(False, mime, tuple(findings), "active or embedded PDF content rejected")
            findings.append(ScanFinding("pdf_active_content", "pass", "no blocked markers"))
            try:
                detail = self.pdf.validate(data)
            except Exception as exc:
                raise ScannerUnavailable("qpdf unavailable or failed closed") from exc
            findings.append(ScanFinding("qpdf", "pass", detail))
        else:
            findings.append(ScanFinding("qpdf", "not_applicable", "non-PDF"))

        try:
            malware_detail = self.malware.scan(data)
        except Exception as exc:
            raise ScannerUnavailable("ClamAV unavailable or failed closed") from exc
        if malware_detail != "clean":
            findings.append(ScanFinding("clamav", "fail", malware_detail))
            return ScanResult(False, mime, tuple(findings), "malware scanner rejected object")
        findings.append(ScanFinding("clamav", "pass", "clean"))
        return ScanResult(True, mime, tuple(findings))
