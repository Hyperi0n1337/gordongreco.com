import pytest

from portal_core.errors import ScannerUnavailable
from portal_core.scanning import ScanPipeline


class Magic:
    def __init__(self, mime="text/plain", error=None): self.mime, self.error = mime, error
    def mime_type(self, data):
        if self.error: raise self.error
        return self.mime


class Malware:
    def __init__(self, result="clean", error=None): self.result, self.error = result, error
    def scan(self, data):
        if self.error: raise self.error
        return self.result


class Pdf:
    def __init__(self, result="qpdf --check passed", error=None): self.result, self.error = result, error
    def validate(self, data):
        if self.error: raise self.error
        return self.result


def pipeline(mime="text/plain", malware="clean", *, magic_error=None, malware_error=None, pdf_error=None):
    return ScanPipeline(Magic(mime, magic_error), Malware(malware, malware_error), Pdf(error=pdf_error))


@pytest.mark.parametrize("body", [b"MZfake", b"\x7fELFfake", b"#!/bin/sh\necho nope"])
def test_executable_signatures_are_rejected_before_type_detection(body):
    result = pipeline().scan(data=body, filename="safe.txt")
    assert not result.clean and "executable" in result.reason.lower() or "script" in result.reason.lower()


def test_executable_mime_and_extension_confusion_are_rejected():
    assert not pipeline("application/x-executable").scan(data=b"not-a-signature", filename="x.txt").clean
    mismatch = pipeline("application/pdf").scan(data=b"%PDF-1.4\n%%EOF", filename="x.txt")
    assert not mismatch.clean and "extension" in mismatch.reason


def test_pdf_active_content_is_rejected():
    result = pipeline("application/pdf").scan(
        data=b"%PDF-1.4\n1 0 obj<</OpenAction 2 0 R>>endobj\n%%EOF", filename="x.pdf"
    )
    assert not result.clean and "active" in result.reason


def test_libmagic_clamav_and_qpdf_fail_closed():
    with pytest.raises(ScannerUnavailable):
        pipeline(magic_error=RuntimeError("down")).scan(data=b"hello", filename="x.txt")
    with pytest.raises(ScannerUnavailable):
        pipeline(malware_error=RuntimeError("down")).scan(data=b"hello", filename="x.txt")
    with pytest.raises(ScannerUnavailable):
        pipeline("application/pdf", pdf_error=RuntimeError("down")).scan(
            data=b"%PDF-1.4\n%%EOF", filename="x.pdf"
        )


def test_malware_result_and_clean_pdf_paths():
    infected = pipeline(malware="Eicar-Test-Signature").scan(data=b"plain", filename="x.txt")
    assert not infected.clean and "malware" in infected.reason
    clean = pipeline("application/pdf").scan(data=b"%PDF-1.4\n%%EOF", filename="x.pdf")
    assert clean.clean and clean.mime_type == "application/pdf"
    controls = {finding.control: finding.result for finding in clean.findings}
    assert controls["qpdf"] == "pass" and controls["clamav"] == "pass"
