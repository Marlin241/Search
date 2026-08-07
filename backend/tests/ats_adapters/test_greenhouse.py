import httpx
import respx

from app.ats_adapters.greenhouse import GreenhouseAdapter
from app.ats_adapters.schemas import DiscoveredForm
from app.models.candidate_profile import CandidateProfile

_SAMPLE_HTML = """
<html><body>
<form action="https://boards-api.greenhouse.io/v1/boards/acme/jobs/123" method="post">
  <input type="hidden" name="authenticity_token" value="tok-gh" />
  <label for="first_name">First Name</label>
  <input type="text" name="job_application[first_name]" id="first_name" required />
  <label for="last_name">Last Name</label>
  <input type="text" name="job_application[last_name]" id="last_name" required />
  <label for="email">Email</label>
  <input type="email" name="job_application[email]" id="email" required />
  <label for="phone">Phone</label>
  <input type="tel" name="job_application[phone]" id="phone" />
  <input type="file" name="job_application[resume]" />
  <label for="q1">Why do you want to work here?</label>
  <textarea name="job_application[answers_attributes][0][text_value]" id="q1"></textarea>
</form>
</body></html>
"""


def _profile() -> CandidateProfile:
    return CandidateProfile(user_id=1, full_name="Jane Doe", phone="0612345678", work_authorization="FR/UE")


@respx.mock
def test_discover_form_maps_greenhouse_field_names():
    respx.get("https://boards.greenhouse.io/acme/jobs/123").mock(return_value=httpx.Response(200, text=_SAMPLE_HTML))

    form = GreenhouseAdapter().discover_form(
        "https://boards.greenhouse.io/acme/jobs/123", _profile(), email="jane@example.com"
    )

    first_name = next(f for f in form.fields if f.name == "job_application[first_name]")
    assert first_name.value == "Jane"
    assert first_name.is_custom is False

    email_field = next(f for f in form.fields if f.name == "job_application[email]")
    assert email_field.value == "jane@example.com"

    custom = next(f for f in form.fields if f.is_custom)
    assert custom.name == "job_application[answers_attributes][0][text_value]"
    assert "Why" in custom.label

    assert form.hidden_fields == {"authenticity_token": "tok-gh"}
    assert form.submit_url == "https://boards-api.greenhouse.io/v1/boards/acme/jobs/123"


@respx.mock
def test_submit_attaches_cv_and_lettre_under_greenhouse_field_names():
    route = respx.post("https://boards-api.greenhouse.io/v1/boards/acme/jobs/123").mock(
        return_value=httpx.Response(200)
    )

    filled = DiscoveredForm(
        submit_url="https://boards-api.greenhouse.io/v1/boards/acme/jobs/123",
        hidden_fields={"authenticity_token": "tok-gh"},
        fields=[],
    )

    GreenhouseAdapter().submit(filled, cv_pdf=b"%PDF-cv", lettre_pdf=b"%PDF-lettre")

    assert route.called
