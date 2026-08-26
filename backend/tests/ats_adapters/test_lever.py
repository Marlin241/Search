import socket
from unittest.mock import patch

import httpx
import pytest
import respx

from app.ats_adapters.errors import ATSAdapterError
from app.ats_adapters.lever import LeverAdapter
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
<form action="https://jobs.lever.co/acme/abc123/apply" method="post">
  <input type="hidden" name="token" value="tok-lever" />
  <label for="name">Full Name</label>
  <input type="text" name="name" id="name" required />
  <label for="email">Email</label>
  <input type="email" name="email" id="email" required />
  <label for="phone">Phone</label>
  <input type="tel" name="phone" id="phone" />
  <input type="file" name="resume" />
  <label for="urls_LinkedIn">LinkedIn</label>
  <input type="text" name="urls[LinkedIn]" id="urls_LinkedIn" />
  <label for="custom1">What interests you about this role?</label>
  <textarea name="customQuestion0" id="custom1"></textarea>
</form>
</body></html>
"""


def _profile() -> CandidateProfile:
    return CandidateProfile(
        user_id=1,
        first_name="Jane",
        last_name="Doe",
        phone="0612345678",
        work_authorization="FR/UE",
        linkedin_url="https://linkedin.com/in/janedoe",
    )


@respx.mock
def test_discover_form_maps_lever_field_names():
    respx.get("https://jobs.lever.co/acme/abc123").mock(
        return_value=httpx.Response(200, text=_SAMPLE_HTML)
    )

    form = LeverAdapter().discover_form(
        "https://jobs.lever.co/acme/abc123", _profile(), email="jane@example.com"
    )

    name_field = next(f for f in form.fields if f.name == "name")
    assert name_field.value == "Jane Doe"  # full name, not just first name
    assert name_field.is_custom is False

    linkedin_field = next(f for f in form.fields if f.name == "urls[LinkedIn]")
    assert linkedin_field.value == "https://linkedin.com/in/janedoe"

    custom = next(f for f in form.fields if f.is_custom)
    assert custom.name == "customQuestion0"
    assert "interests" in custom.label

    assert form.hidden_fields == {"token": "tok-lever"}
    assert form.submit_url == "https://jobs.lever.co/acme/abc123/apply"


@respx.mock
def test_submit_attaches_cv_and_lettre_under_lever_field_names():
    route = respx.post("https://jobs.lever.co/acme/abc123/apply").mock(
        return_value=httpx.Response(200)
    )

    filled = DiscoveredForm(
        submit_url="https://jobs.lever.co/acme/abc123/apply",
        hidden_fields={"token": "tok-lever"},
        fields=[],
    )

    LeverAdapter().submit(filled, cv_pdf=b"%PDF-cv", lettre_pdf=b"%PDF-lettre")

    assert route.called

    # Extract multipart boundary from Content-Type header
    content_type = route.calls[0].request.headers["content-type"]
    boundary = content_type.split("boundary=")[1]

    # Parse multipart body to get field-to-content mapping
    sent_body = route.calls[0].request.content
    parts = _parse_multipart_parts(sent_body, boundary)

    # Verify CV is attached under correct Lever field name
    assert "resume" in parts
    assert b"%PDF-cv" in parts["resume"]
    assert b"%PDF-lettre" not in parts["resume"]

    # Verify cover letter is attached under correct Lever field name
    assert "coverLetter" in parts
    assert b"%PDF-lettre" in parts["coverLetter"]
    assert b"%PDF-cv" not in parts["coverLetter"]


# See the equivalent constant in test_greenhouse.py: a public address so
# the SSRF check passes and only the host-allowlist check can reject.
_PUBLIC_ADDRINFO = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


@respx.mock
def test_discover_form_rejects_a_non_lever_host():
    route = respx.get("https://attacker.example.com/harvest").mock(
        return_value=httpx.Response(200, text=_SAMPLE_HTML)
    )

    with (
        patch(
            "app.offer_ingestion.scraper.socket.getaddrinfo",
            return_value=_PUBLIC_ADDRINFO,
        ),
        pytest.raises(ATSAdapterError),
    ):
        LeverAdapter().discover_form(
            "https://attacker.example.com/harvest", _profile(), email="jane@example.com"
        )

    assert not route.called


@respx.mock
def test_discover_form_rejects_a_lookalike_lever_host():
    route = respx.get("https://notlever.co/acme/abc123").mock(
        return_value=httpx.Response(200, text=_SAMPLE_HTML)
    )

    with (
        patch(
            "app.offer_ingestion.scraper.socket.getaddrinfo",
            return_value=_PUBLIC_ADDRINFO,
        ),
        pytest.raises(ATSAdapterError),
    ):
        LeverAdapter().discover_form(
            "https://notlever.co/acme/abc123", _profile(), email="jane@example.com"
        )

    assert not route.called


@respx.mock
def test_submit_rejects_a_non_lever_submit_url():
    route = respx.post("https://attacker.example.com/harvest").mock(
        return_value=httpx.Response(200)
    )
    filled = DiscoveredForm(
        submit_url="https://attacker.example.com/harvest", hidden_fields={}, fields=[]
    )

    with (
        patch(
            "app.offer_ingestion.scraper.socket.getaddrinfo",
            return_value=_PUBLIC_ADDRINFO,
        ),
        pytest.raises(ATSAdapterError),
    ):
        LeverAdapter().submit(filled, cv_pdf=b"%PDF-cv", lettre_pdf=b"%PDF-lettre")

    assert not route.called
