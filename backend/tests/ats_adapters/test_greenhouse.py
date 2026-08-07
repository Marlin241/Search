import httpx
import respx

from app.ats_adapters.greenhouse import GreenhouseAdapter
from app.ats_adapters.schemas import DiscoveredForm
from app.models.candidate_profile import CandidateProfile


def _parse_multipart_parts(content: bytes, boundary: str) -> dict[str, bytes]:
    """Parse multipart form data into a dict mapping field names to their content.

    Args:
        content: Raw multipart request body
        boundary: Multipart boundary (without dashes)

    Returns:
        Dict mapping field names (extracted from name="...") to part content
    """
    boundary_bytes = b"--" + boundary.encode()
    parts = {}

    for part_data in content.split(boundary_bytes):
        if not part_data or part_data.startswith(b"--"):
            continue

        # Split headers from body (separated by double CRLF)
        if b"\r\n\r\n" in part_data:
            headers_section, body = part_data.split(b"\r\n\r\n", 1)
        else:
            continue

        # Parse Content-Disposition header to extract field name
        headers_str = headers_section.decode("utf-8", errors="ignore")
        if 'name="' in headers_str:
            # Extract field name from: name="field_name"
            start = headers_str.find('name="') + 6
            end = headers_str.find('"', start)
            field_name = headers_str[start:end]

            # Store the body content (strip trailing CRLF)
            parts[field_name] = body.rstrip(b"\r\n")

    return parts

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

    # Extract multipart boundary from Content-Type header
    content_type = route.calls[0].request.headers["content-type"]
    boundary = content_type.split("boundary=")[1]

    # Parse multipart body to get field-to-content mapping
    sent_body = route.calls[0].request.content
    parts = _parse_multipart_parts(sent_body, boundary)

    # Verify CV is attached under correct Greenhouse field name
    assert "job_application[resume]" in parts
    assert b"%PDF-cv" in parts["job_application[resume]"]
    assert b"%PDF-lettre" not in parts["job_application[resume]"]

    # Verify cover letter is attached under correct Greenhouse field name
    assert "job_application[cover_letter]" in parts
    assert b"%PDF-lettre" in parts["job_application[cover_letter]"]
    assert b"%PDF-cv" not in parts["job_application[cover_letter]"]
