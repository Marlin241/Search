import io

from docx import Document

from app.cv_parser.parser import MAX_CV_SIZE_BYTES
from app.llm_analyzer.analyzer import SemanticReport
from app.llm_analyzer.dependencies import get_semantic_analyzer
from app.main import app
from app.rate_limit.limiter import MAX_DIAGNOSTICS_PER_HOUR


class FakeAnalyzer:
    def analyze(self, cv_text: str, offer_text: str) -> SemanticReport:
        return SemanticReport(score=60, missing_keywords=["Docker"], recommendations=["Add Docker"])


def _clean_cv_docx_bytes() -> bytes:
    document = Document()
    document.add_paragraph("Expérience professionnelle")
    document.add_paragraph("Développeur")
    document.add_paragraph("Formation")
    document.add_paragraph("Master")
    document.add_paragraph("Compétences")
    document.add_paragraph("Python")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _register_and_login(client) -> str:
    client.post("/auth/register", json={"email": "jane@example.com", "password": "s3cret!1"})
    login = client.post("/auth/login", data={"username": "jane@example.com", "password": "s3cret!1"})
    return login.json()["access_token"]


def test_create_diagnostic_returns_combined_report(client):
    app.dependency_overrides[get_semantic_analyzer] = lambda: FakeAnalyzer()
    token = _register_and_login(client)

    response = client.post(
        "/diagnostics",
        headers={"Authorization": f"Bearer {token}"},
        files={"cv_file": ("cv.docx", _clean_cv_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"offer_text": "We need a Python developer with Docker experience."},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["structural_score"] == 100
    assert body["semantic_score"] == 60
    assert body["overall_score"] == 80
    assert body["missing_keywords"] == ["Docker"]

    app.dependency_overrides.pop(get_semantic_analyzer, None)


def test_create_diagnostic_without_offer_returns_422(client):
    app.dependency_overrides[get_semantic_analyzer] = lambda: FakeAnalyzer()
    token = _register_and_login(client)

    response = client.post(
        "/diagnostics",
        headers={"Authorization": f"Bearer {token}"},
        files={"cv_file": ("cv.docx", _clean_cv_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert response.status_code == 422
    app.dependency_overrides.pop(get_semantic_analyzer, None)


def test_list_and_delete_diagnostics(client):
    app.dependency_overrides[get_semantic_analyzer] = lambda: FakeAnalyzer()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        "/diagnostics",
        headers=headers,
        files={"cv_file": ("cv.docx", _clean_cv_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"offer_text": "We need a Python developer."},
    )

    listed = client.get("/diagnostics", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    deleted = client.delete("/diagnostics", headers=headers)
    assert deleted.status_code == 204

    listed_after = client.get("/diagnostics", headers=headers)
    assert listed_after.json() == []

    app.dependency_overrides.pop(get_semantic_analyzer, None)


def test_create_diagnostic_oversized_cv_returns_422(client):
    app.dependency_overrides[get_semantic_analyzer] = lambda: FakeAnalyzer()
    token = _register_and_login(client)

    oversized_bytes = b"a" * (MAX_CV_SIZE_BYTES + 1)
    response = client.post(
        "/diagnostics",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "cv_file": (
                "cv.docx",
                oversized_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"offer_text": "We need a Python developer with Docker experience."},
    )

    assert response.status_code == 422

    app.dependency_overrides.pop(get_semantic_analyzer, None)


def test_create_diagnostic_oversized_offer_text_returns_422(client):
    app.dependency_overrides[get_semantic_analyzer] = lambda: FakeAnalyzer()
    token = _register_and_login(client)

    response = client.post(
        "/diagnostics",
        headers={"Authorization": f"Bearer {token}"},
        files={"cv_file": ("cv.docx", _clean_cv_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"offer_text": "a" * 50001},
    )

    assert response.status_code == 422

    app.dependency_overrides.pop(get_semantic_analyzer, None)


def test_rate_limit_returns_429(client):
    app.dependency_overrides[get_semantic_analyzer] = lambda: FakeAnalyzer()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    for _ in range(MAX_DIAGNOSTICS_PER_HOUR):
        response = client.post(
            "/diagnostics",
            headers=headers,
            files={"cv_file": ("cv.docx", _clean_cv_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"offer_text": "We need a Python developer."},
        )
        assert response.status_code == 201

    blocked = client.post(
        "/diagnostics",
        headers=headers,
        files={"cv_file": ("cv.docx", _clean_cv_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"offer_text": "We need a Python developer."},
    )
    assert blocked.status_code == 429

    app.dependency_overrides.pop(get_semantic_analyzer, None)
