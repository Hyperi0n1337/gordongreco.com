from __future__ import annotations

from fastapi.testclient import TestClient

from apps.demo import server


def test_ann_demo_registration_upload_and_logout(monkeypatch) -> None:
    server.INVITATION_CONSUMED = False
    server.MAGIC_LINKS.clear()
    server.SEND_TIMES.clear()
    server.UPLOADS.clear()
    server.DOCUMENTS.clear()
    delivered = {}
    monkeypatch.setattr(
        server,
        "_deliver_magic_link",
        lambda **kwargs: delivered.update(kwargs) or {"message_id": "gmail-test-message"},
    )
    with TestClient(server.app, base_url="http://127.0.0.1:8520") as client:
        demo_link = client.post(
            "/api/v1/auth/magic-link", json={"email": "arhra1337@gmail.com"}
        )
        assert demo_link.status_code == 202
        assert demo_link.json()["delivery"] == "sent"
        assert delivered["recipient"] == "arhra1337@gmail.com"
        assert delivered["display_name"] == "Robert Tharp (test delivery)"
        token = next(iter(server.MAGIC_LINKS))

        registered = client.post(
            "/api/v1/auth/magic-link/consume",
            json={"token": token},
            headers={"Origin": "http://127.0.0.1:8520"},
        )
        assert registered.status_code == 200
        assert client.post(
            "/api/v1/auth/magic-link/consume", json={"token": token}
        ).status_code == 401

        me = client.get("/api/v1/me")
        assert me.status_code == 200
        assert me.json()["user"]["email"] == "arhra1337@gmail.com"
        assert me.json()["household_ids"] == ["robert-tharp.test"]
        csrf = client.cookies["gg_csrf"]
        headers = {"X-CSRF-Token": csrf}

        started = client.post(
            "/api/v1/uploads",
            headers=headers,
            json={
                "request_id": "ann-id-document.test",
                "filename": "fictional.txt",
                "content_type": "text/plain",
                "size": 10,
                "idempotency_key": "demo-test",
            },
        )
        upload_id = started.json()["upload_id"]
        capability = client.post(
            f"/api/v1/uploads/{upload_id}/parts/1/capability", headers=headers
        ).json()["capability"]
        part = client.put(
            f"/api/v1/uploads/{upload_id}/parts/1",
            headers={**headers, "X-Upload-Capability": capability},
            content=b"fictional!",
        )
        assert part.status_code == 200
        completed = client.post(
            f"/api/v1/uploads/{upload_id}/complete",
            headers=headers,
            json={"parts": [{"part_number": 1, "etag": part.json()["etag"]}]},
        )
        assert completed.status_code == 200
        assert completed.json()["state"] == "quarantined"

        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
        assert client.get("/api/v1/me").status_code == 401


def test_robert_and_evan_test_links_are_household_isolated(monkeypatch) -> None:
    server.MAGIC_LINKS.clear()
    server.SESSIONS.clear()
    server.SEND_TIMES.clear()
    server.UPLOADS.clear()
    monkeypatch.setattr(
        server,
        "_deliver_magic_link",
        lambda **_: {"message_id": "gmail-test-message"},
    )
    with (
        TestClient(server.app, base_url="http://127.0.0.1:8520") as robert,
        TestClient(server.app, base_url="http://127.0.0.1:8520") as evan,
    ):
        robert.post("/api/v1/auth/magic-link", json={"email": "arhra1337@gmail.com"})
        robert_token = next(reversed(server.MAGIC_LINKS))
        evan.post(
            "/api/v1/auth/magic-link",
            json={"email": "baldleggedcutlet@protonmail.com"},
        )
        evan_token = next(reversed(server.MAGIC_LINKS))
        assert robert.post(
            "/api/v1/auth/magic-link/consume", json={"token": robert_token}
        ).status_code == 200
        assert evan.post(
            "/api/v1/auth/magic-link/consume", json={"token": evan_token}
        ).status_code == 200
        assert robert.get("/api/v1/me").json()["household_ids"] == ["robert-tharp.test"]
        assert evan.get("/api/v1/me").json()["household_ids"] == ["evan-emma-carroll.test"]

        csrf = robert.cookies["gg_csrf"]
        started = robert.post(
            "/api/v1/uploads",
            headers={"X-CSRF-Token": csrf},
            json={
                "request_id": "ann-id-document.test",
                "filename": "robert-test.txt",
                "content_type": "text/plain",
                "size": 4,
                "idempotency_key": "robert-isolation",
            },
        )
        assert started.status_code == 201
        assert evan.get(f"/api/v1/uploads/{started.json()['upload_id']}").status_code == 404
