from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.errors import register_exception_handlers


def _app():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internals")

    @app.get("/teapot")
    def teapot():
        raise HTTPException(status_code=418, detail="Je suis une théière.")

    return app


def test_unhandled_exception_returns_generic_500():
    client = TestClient(_app(), raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert body["detail"] == "Une erreur est survenue. L'équipe a été notifiée."
    assert "secret internals" not in resp.text
    assert "error_id" in body


def test_http_exception_is_untouched():
    client = TestClient(_app(), raise_server_exceptions=False)
    resp = client.get("/teapot")
    assert resp.status_code == 418
    assert resp.json()["detail"] == "Je suis une théière."
