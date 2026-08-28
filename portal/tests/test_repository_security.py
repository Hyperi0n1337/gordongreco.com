from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SITE = ROOT.parent / "web"


def test_public_marketing_site_and_private_portal_are_separate_apps():
    assert (PUBLIC_SITE / "index.html").is_file()
    assert (ROOT / "apps/portal-web/index.html").is_file()
    assert not (ROOT / "apps/public-site").exists()
    public_shell = (PUBLIC_SITE / "client.html").read_text().lower()
    assert "noindex" in public_shell
    assert "portal-web" not in public_shell


def test_private_ui_does_not_persist_sessions_in_browser_storage():
    ui = "\n".join(p.read_text() for p in (ROOT / "apps/portal-web").glob("*.js"))
    assert "localStorage" not in ui
    # Session storage is limited to opaque, non-authorizing upload IDs for crash recovery.
    assert ui.count("sessionStorage") <= 4
    assert "gg-upload:" in ui
    assert "credentials: 'same-origin'" in ui or "credentials: \"same-origin\"" in ui
    assert "X-CSRF-Token" in ui
    client = (ROOT / "apps/portal-web/client.js").read_text()
    assert "uploaded_bytes" in client and "/parts/" in client and "remoteParts" in client


def test_fixtures_are_explicitly_fictional_and_no_secret_files_are_packaged():
    fixture_files = [p for p in (ROOT / "fixtures").rglob("*") if p.is_file()]
    assert fixture_files
    assert all(".test" in p.name or p.name == "README.md" for p in fixture_files)
    text = "\n".join(p.read_text(errors="ignore") for p in fixture_files)
    assert "example.test" in text and "fictional" in text.lower()
    forbidden_names = {".env", "id_rsa", "credentials.json", "token.json", "browser_profile"}
    assert not any(p.name in forbidden_names for p in ROOT.rglob("*"))


def test_no_input_archive_or_nested_zip_is_in_repository():
    zips = list(ROOT.rglob("*.zip"))
    assert zips == []
    assert not any("GORDON_GRECO_WEBSITE_AND_PORTAL_CONTEXT" in str(p) for p in ROOT.rglob("*"))


def test_manifest_and_acceptance_files_are_machine_readable_when_generated():
    for name in ["implementation_manifest.json", "context_manifest.json", "acceptance_matrix.json"]:
        path = ROOT / name
        if path.exists():
            parsed = json.loads(path.read_text())
            assert isinstance(parsed, dict)
