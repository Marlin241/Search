import io

import httpx
import respx
from docx import Document

from app.ats_adapters.custom_fields import CustomFieldAnswerer
from app.ats_adapters.dependencies import get_custom_field_answerer
from app.llm_analyzer.analyzer import SemanticReport
from app.llm_analyzer.dependencies import get_semantic_analyzer
from app.main import app
from app.personalization.dependencies import get_cover_letter_generator, get_cv_rewriter
from app.personalization.schemas import CoverLetter, CvExperienceEntry, RewrittenCv
from app.storage.client import ObjectStorage, ObjectStorageError
from app.storage.dependencies import get_object_storage

_GREENHOUSE_FORM_HTML = """
<html><body>
<form action="https://boards-api.greenhouse.io/v1/boards/acme/jobs/123" method="post">
  <input type="hidden" name="authenticity_token" value="tok-gh" />
  <label for="first_name">First Name</label>
  <input type="text" name="job_application[first_name]" id="first_name" required />
  <label for="email">Email</label>
  <input type="email" name="job_application[email]" id="email" required />
  <input type="file" name="job_application[resume]" />
  <label for="q1">Why do you want to work here?</label>
  <textarea name="job_application[answers_attributes][0][text_value]" id="q1"></textarea>
</form>
</body></html>
"""


class FakeAnalyzer:
    def analyze(self, cv_text, offer_text):
        return SemanticReport(score=70, missing_keywords=["Docker"], recommendations=["Add Docker"])


class FakeCvRewriter:
    def rewrite(self, cv_text, offer_text, missing_keywords, recommendations):
        return RewrittenCv(
            summary="Résumé.",
            experience=[CvExperienceEntry(title="Dev", company="Acme", dates="2020-2022", bullets=["A conçu des API."])],
            education=["Master"],
            skills=["Python"],
        )


class FakeCoverLetterGenerator:
    def generate(self, cv_text, offer_text, missing_keywords, recommendations):
        return CoverLetter(
            greeting="Madame, Monsieur,",
            body_paragraphs=["Je candidate à ce poste."],
            closing_formula="Cordialement,",
            signature="Jane Doe",
        )


class FakeCustomFieldAnswerer(CustomFieldAnswerer):
    def __init__(self):
        pass

    def answer(self, custom_fields, cv_text, offer_text):
        return {f.name: "Réponse générée." for f in custom_fields}


class FakeObjectStorage(ObjectStorage):
    def __init__(self):
        self._objects: dict[str, bytes] = {}

    def upload(self, key, content):
        self._objects[key] = content

    def download(self, key):
        if key not in self._objects:
            raise ObjectStorageError(f"missing {key}")
        return self._objects[key]

    def delete(self, key):
        self._objects.pop(key, None)


def _register_and_login(client, email: str = "jane@example.com") -> str:
    client.post("/auth/register", json={"email": email, "password": "s3cret!1"})
    login = client.post("/auth/login", data={"username": email, "password": "s3cret!1"})
    return login.json()["access_token"]


def _cv_docx_bytes() -> bytes:
    document = Document()
    document.add_paragraph("Jane Doe - Développeuse Python")
    document.add_paragraph("Expérience professionnelle")
    document.add_paragraph("Développeuse Python chez Acme, 2020-2022. A conçu des API REST avec FastAPI.")
    document.add_paragraph("Compétences: Python, SQL, Docker.")
    document.add_paragraph("Formation: Master informatique.")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _setup_profile(client, headers: dict) -> None:
    client.put(
        "/profile", headers=headers,
        json={"full_name": "Jane Doe", "phone": "0612345678", "work_authorization": "FR/UE"},
    )
    client.post(
        "/profile/cv", headers=headers,
        files={"cv_file": ("cv.docx", _cv_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )


def _setup_ready_ats_application(client, headers: dict) -> int:
    _setup_profile(client, headers)
    created = client.post(
        "/applications", headers=headers,
        json={
            "offer_url": "https://boards.greenhouse.io/acme/jobs/123",
            "offer_text": "Nous recherchons un développeur Python.",
            "source": "greenhouse",
            "company_name": "Acme",
            "job_title": "Développeur Python",
            "ats_type": "greenhouse",
        },
    )
    application_id = created.json()["id"]
    diagnostic_id = created.json()["diagnostic_id"]
    client.post(f"/diagnostics/{diagnostic_id}/cv", headers=headers)
    client.post(f"/diagnostics/{diagnostic_id}/lettre", headers=headers)
    return application_id


def _override_common_dependencies() -> None:
    # get_object_storage is a single @lru_cache singleton for the app's
    # lifetime in production, so uploads made by one request (e.g. CV/lettre
    # generation) are visible to a later request's download (e.g. confirm).
    # A fresh FakeObjectStorage() per Depends() resolution would break that:
    # each request would see an empty store. One shared instance per test
    # reproduces the real singleton behavior.
    fake_storage = FakeObjectStorage()
    app.dependency_overrides[get_semantic_analyzer] = lambda: FakeAnalyzer()
    app.dependency_overrides[get_cv_rewriter] = lambda: FakeCvRewriter()
    app.dependency_overrides[get_cover_letter_generator] = lambda: FakeCoverLetterGenerator()
    app.dependency_overrides[get_object_storage] = lambda: fake_storage
    app.dependency_overrides[get_custom_field_answerer] = lambda: FakeCustomFieldAnswerer()


@respx.mock
def test_get_prefilled_form_returns_standard_and_llm_answered_custom_fields(client):
    _override_common_dependencies()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    application_id = _setup_ready_ats_application(client, headers)
    respx.get("https://boards.greenhouse.io/acme/jobs/123").mock(return_value=httpx.Response(200, text=_GREENHOUSE_FORM_HTML))

    response = client.get(f"/applications/{application_id}/prefilled-form", headers=headers)

    assert response.status_code == 200
    fields = response.json()["fields"]
    first_name = next(f for f in fields if f["name"] == "job_application[first_name]")
    assert first_name["value"] == "Jane"
    custom = next(f for f in fields if f["is_custom"])
    assert custom["value"] == "Réponse générée."


def test_get_prefilled_form_returns_409_for_non_ats_offer(client):
    _override_common_dependencies()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile(client, headers)
    created = client.post(
        "/applications", headers=headers,
        json={
            "offer_url": "https://www.linkedin.com/jobs/view/123",
            "offer_text": "Offre.",
            "source": "manual",
            "company_name": "Acme",
            "job_title": "Dev",
        },
    )
    response = client.get(f"/applications/{created.json()['id']}/prefilled-form", headers=headers)
    assert response.status_code == 409


@respx.mock
def test_confirm_application_auto_submits_for_ats_offer(client):
    _override_common_dependencies()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    application_id = _setup_ready_ats_application(client, headers)
    respx.get("https://boards.greenhouse.io/acme/jobs/123").mock(return_value=httpx.Response(200, text=_GREENHOUSE_FORM_HTML))
    submit_route = respx.post("https://boards-api.greenhouse.io/v1/boards/acme/jobs/123").mock(return_value=httpx.Response(200))

    prefilled = client.get(f"/applications/{application_id}/prefilled-form", headers=headers).json()
    response = client.post(f"/applications/{application_id}/confirm", headers=headers, json={"fields": prefilled["fields"]})

    assert response.status_code == 200
    assert response.json()["status"] == "soumise_auto"
    assert submit_route.called


@respx.mock
def test_confirm_application_records_failure_status_on_submission_error(client):
    _override_common_dependencies()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    application_id = _setup_ready_ats_application(client, headers)
    respx.get("https://boards.greenhouse.io/acme/jobs/123").mock(return_value=httpx.Response(200, text=_GREENHOUSE_FORM_HTML))
    respx.post("https://boards-api.greenhouse.io/v1/boards/acme/jobs/123").mock(return_value=httpx.Response(500))

    prefilled = client.get(f"/applications/{application_id}/prefilled-form", headers=headers).json()
    response = client.post(f"/applications/{application_id}/confirm", headers=headers, json={"fields": prefilled["fields"]})

    assert response.status_code == 503
    detail = client.get(f"/applications/{application_id}", headers=headers).json()
    assert detail["status"] == "echec_soumission"
    assert detail["error_message"] is not None


def test_confirm_application_without_ats_type_moves_to_assisted_status(client):
    _override_common_dependencies()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile(client, headers)
    created = client.post(
        "/applications", headers=headers,
        json={
            "offer_url": "https://www.linkedin.com/jobs/view/123",
            "offer_text": "Offre.",
            "source": "manual",
            "company_name": "Acme",
            "job_title": "Dev",
        },
    )
    application_id = created.json()["id"]

    response = client.post(f"/applications/{application_id}/confirm", headers=headers, json={})

    assert response.status_code == 200
    assert response.json()["status"] == "a_soumettre_manuellement"


def test_mark_sent_manually_transitions_status(client):
    _override_common_dependencies()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile(client, headers)
    created = client.post(
        "/applications", headers=headers,
        json={
            "offer_url": "https://www.linkedin.com/jobs/view/123",
            "offer_text": "Offre.",
            "source": "manual",
            "company_name": "Acme",
            "job_title": "Dev",
        },
    )
    application_id = created.json()["id"]
    client.post(f"/applications/{application_id}/confirm", headers=headers, json={})

    response = client.post(f"/applications/{application_id}/mark-sent", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "soumise_manuelle_confirmee"


def test_mark_sent_manually_rejects_wrong_state(client):
    _override_common_dependencies()
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    application_id = _setup_ready_ats_application(client, headers)  # still "en_cours", never confirmed

    response = client.post(f"/applications/{application_id}/mark-sent", headers=headers)
    assert response.status_code == 409
