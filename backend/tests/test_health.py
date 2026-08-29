import os

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")


def test_health_ok_reports_db_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert "version" in body


def test_health_degraded_when_db_unavailable(client, monkeypatch):
    from app import main

    def _boom(_db):
        raise RuntimeError("db down")

    monkeypatch.setattr(main, "_probe_db", _boom)
    resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.json()["db"] == "error"
