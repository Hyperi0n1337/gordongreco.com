#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SITE = ROOT.parent / "web"


def run(command: list[str], *, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
    output = (result.stdout + result.stderr).strip()
    if result.returncode:
        raise AssertionError(f"command failed ({result.returncode}): {' '.join(command)}\n{output}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-write", action="store_true", help="verify without regenerating manifests/logs")
    parser.parse_args()
    required = [
        "README.md", "VERIFY.md", "implementation_manifest.json", "context_manifest.json",
        "acceptance_matrix.json", "acceptance_matrix.md",
        "apps/portal-web/index.html",
        "apps/api/portal_api/main.py", "apps/worker/portal_worker/main.py",
        "migrations/0009_worker_immutability.sql", "docs/THREAT_MODEL.md",
        "docs/INCIDENT_RESPONSE.md", "docs/BACKUP_RECOVERY.md", "docs/BOOKS_AND_RECORDS_DECISIONS.md",
    ]
    for rel in required:
        assert (ROOT / rel).is_file(), f"required file missing: {rel}"
    assert (PUBLIC_SITE / "index.html").is_file(), "canonical public site is missing"
    assert (PUBLIC_SITE / "client.html").is_file(), "canonical public client shell is missing"
    assert not (ROOT / "apps/public-site").exists(), "private portal must not duplicate the public-site owner"

    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT).as_posix()
        assert not path.is_symlink(), f"symlink forbidden: {rel}"
        assert path.name not in {".env", "id_rsa", "id_ed25519", "credentials.json", "token.json"}, f"secret artifact: {rel}"
        assert "__pycache__" not in path.parts and path.suffix != ".pyc", f"bytecode artifact: {rel}"
        assert path.suffix.lower() != ".zip", f"nested archive forbidden: {rel}"

    manifest = json.loads((ROOT / "implementation_manifest.json").read_text())
    assert manifest["prompt_id"] == "MAS-RP-402"
    for item in manifest["files"]:
        path = ROOT / item["path"]
        assert path.is_file(), f"manifest file missing: {item['path']}"
        body = path.read_bytes()
        assert len(body) == item["bytes"], f"manifest size mismatch: {item['path']}"
        assert hashlib.sha256(body).hexdigest() == item["sha256"], f"manifest hash mismatch: {item['path']}"

    context = json.loads((ROOT / "context_manifest.json").read_text())
    assert context["read_status"] == "complete"
    assert context["member_count"] == len(context["members"]) >= 50
    assert context["public_site_copy_verification"]["status"] == "PASS"
    acceptance = json.loads((ROOT / "acceptance_matrix.json").read_text())
    assert all(row["status"] == "PASS" for row in acceptance["requirements"])

    for path in ROOT.rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    print(f"PASS: parsed {len(list(ROOT.rglob('*.py')))} Python files")

    print(run([sys.executable, "scripts/check_migrations.py"]))
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(["packages", "apps/api", "apps/worker"])
    print(run([sys.executable, "-m", "pytest", "-q"], env=env))
    if shutil.which("node"):
        for rel in ["apps/portal-web/api.js", "apps/portal-web/client.js", "apps/portal-web/advisor.js"]:
            run(["node", "--check", rel])
        print("PASS: Node syntax check for 3 private-portal JavaScript files")
    else:
        print("NOT-RUN: Node syntax check (node unavailable)")

    public_shell = (PUBLIC_SITE / "client.html").read_text(errors="ignore").lower()
    private_js = "\n".join(p.read_text(errors="ignore") for p in (ROOT / "apps/portal-web").glob("*.js"))
    assert "noindex" in public_shell and "portal-web" not in public_shell
    assert "localStorage" not in private_js
    assert "X-CSRF-Token" in private_js and "gg-upload:" in private_js
    fixture_paths = [p for p in (ROOT / "fixtures").rglob("*") if p.is_file()]
    assert fixture_paths and all(".test" in p.name or p.name == "README.md" for p in fixture_paths)
    print(f"PASS: repository controls, {len(fixture_paths)} fictional fixture files, public/private boundary")
    print("VERIFY PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
