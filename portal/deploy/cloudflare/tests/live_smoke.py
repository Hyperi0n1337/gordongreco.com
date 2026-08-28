#!/usr/bin/env python3
"""Live, fictional Cloudflare portal acceptance smoke test."""

from __future__ import annotations

import json
import secrets
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path


BASE = "https://gordon-greco-client-portal.markterzidis.workers.dev"
ADMIN_KEY = Path("/home/markos/.config/gordon-greco-portal/admin_api_key")
UA = "OpenAI File Downloader, XaiImageApiFetch/1.0"


def call(opener, path, *, method="GET", body=None, headers=None, expected=200):
    data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    request = urllib.request.Request(BASE + path, data=data, method=method)
    request.add_header("User-Agent", UA)
    if body is not None and not isinstance(body, bytes):
        request.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        response = opener.open(request, timeout=30)
        status, raw, response_headers = response.status, response.read(), response.headers
    except urllib.error.HTTPError as error:
        status, raw, response_headers = error.code, error.read(), error.headers
    assert status == expected, (path, status, raw[:200])
    return (json.loads(raw) if raw and "json" in response_headers.get("content-type", "") else raw), response_headers


def csrf(jar):
    return next(cookie.value for cookie in jar if cookie.name == "gg_csrf")


def multipart(request_id, name, content_type, body):
    boundary = "----gg" + secrets.token_hex(12)
    raw = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"request_id\"\r\n\r\n{request_id}\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + body + f"\r\n--{boundary}--\r\n".encode()
    return raw, f"multipart/form-data; boundary={boundary}"


def main():
    admin_key = ADMIN_KEY.read_text().strip()
    public = urllib.request.build_opener()
    admin_headers = {"Authorization": f"Bearer {admin_key}"}
    call(public, "/api/v1/me", expected=401)
    call(public, "/api/v1/auth/invitation/consume", method="POST", body={"token": "invalid"}, expected=401)
    call(public, "/api/v1/admin/documents", headers={"Authorization": "Bearer wrong"}, expected=401)

    run = secrets.token_hex(6)
    households = []
    for index in (1, 2):
        household = f"smoke-{run}-{index}"
        request_id = f"request-{run}-{index}"
        invite, _ = call(
            public,
            "/api/v1/admin/invitations",
            method="POST",
            headers=admin_headers,
            body={
                "email": f"portal-smoke-{run}-{index}@example.test",
                "display_name": f"Smoke Client {index}",
                "household_id": household,
                "household_name": f"Smoke Household {index}",
                "expires_in_seconds": 600,
                "document_requests": [{"id": request_id, "title": "Fictional statement", "description": "Synthetic smoke fixture"}],
            },
            expected=201,
        )
        token = invite["invitation_url"].split("token=", 1)[1]
        jar = CookieJar()
        client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        call(client, "/api/v1/auth/invitation/consume", method="POST", body={"token": token})
        me, _ = call(client, "/api/v1/me")
        assert me["household_id"] == household
        checklist, _ = call(client, "/api/v1/document-requests")
        assert [row["id"] for row in checklist["items"]] == [request_id]
        households.append((client, jar, request_id))

    first, first_jar, first_request = households[0]
    second_request = households[1][2]
    cross_body, cross_type = multipart(second_request, "cross.txt", "text/plain", b"cross")
    call(first, "/api/v1/uploads", method="POST", body=cross_body, headers={"Content-Type": cross_type, "X-CSRF-Token": csrf(first_jar)}, expected=404)
    bad_body, bad_type = multipart(first_request, "bad.exe", "application/octet-stream", b"MZ")
    call(first, "/api/v1/uploads", method="POST", body=bad_body, headers={"Content-Type": bad_type, "X-CSRF-Token": csrf(first_jar)}, expected=415)
    good_body, good_type = multipart(first_request, "fictional.test.txt", "text/plain", b"fictional portal smoke fixture")
    uploaded, _ = call(first, "/api/v1/uploads", method="POST", body=good_body, headers={"Content-Type": good_type, "X-CSRF-Token": csrf(first_jar)}, expected=201)
    assert uploaded["status"] == "quarantined" and len(uploaded["sha256"]) == 64

    documents, _ = call(public, "/api/v1/admin/documents", headers=admin_headers)
    document = next(row for row in documents["documents"] if row["id"] == uploaded["document_id"])
    content, headers = call(public, f"/api/v1/admin/documents/{document['id']}/download", headers=admin_headers)
    assert content == b"fictional portal smoke fixture"
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("content-disposition", "").startswith("attachment;")
    call(public, f"/api/v1/admin/documents/{document['id']}/review", method="POST", headers=admin_headers, body={"decision": "accepted", "expected_revision": 1})
    call(public, f"/api/v1/admin/documents/{document['id']}/review", method="POST", headers=admin_headers, body={"decision": "accepted", "expected_revision": 1}, expected=409)
    call(first, "/api/v1/auth/logout", method="POST", headers={"X-CSRF-Token": csrf(first_jar)}, expected=204)
    call(first, "/api/v1/me", expected=401)
    print("PASS: live invitation, two-household isolation, CSRF, type denial, quarantine, safe download, revision conflict, and logout")
    return 0


if __name__ == "__main__":
    sys.exit(main())
