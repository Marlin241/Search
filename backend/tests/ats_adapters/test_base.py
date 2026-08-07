import httpx
import pytest
import respx

from app.ats_adapters.base import HtmlFormAdapter
from app.ats_adapters.errors import ATSAdapterError
from app.ats_adapters.schemas import DiscoveredForm, FormField
from app.models.candidate_profile import CandidateProfile

_SAMPLE_FORM_HTML = """
<html><body>
<form action="/submit" method="post">
  <input type="hidden" name="csrf_token" value="tok-abc" />
  <label for="fname">First name</label>
  <input type="text" name="first_name" id="fname" required />
  <label for="lname">Last name</label>
  <input type="text" name="last_name" id="lname" />
  <label for="email_field">Email</label>
  <input type="email" name="email" id="email_field" required />
  <input type="file" name="resume" />
  <label for="why">Why this role?</label>
  <textarea name="custom_why" id="why"></textarea>
</form>
</body></html>
"""


class _TestAdapter(HtmlFormAdapter):
    standard_field_aliases = {
        "first_name": ["first_name"],
        "last_name": ["last_name"],
        "email": ["email"],
    }
    resume_field_names = ["resume"]
    cover_letter_field_names = ["cover_letter"]


def _profile() -> CandidateProfile:
    return CandidateProfile(user_id=1, full_name="Jane Doe", phone="0600000000", work_authorization="FR/UE")


@respx.mock
def test_discover_form_splits_standard_and_custom_fields():
    respx.get("https://example.com/apply").mock(return_value=httpx.Response(200, text=_SAMPLE_FORM_HTML))

    form = _TestAdapter().discover_form("https://example.com/apply", _profile(), email="jane@example.com")

    assert form.submit_url == "https://example.com/submit"
    assert form.hidden_fields == {"csrf_token": "tok-abc"}
    field_names = {f.name for f in form.fields}
    assert field_names == {"first_name", "last_name", "email", "custom_why"}
    assert "resume" not in field_names  # file inputs are never fillable text fields

    first_name_field = next(f for f in form.fields if f.name == "first_name")
    assert first_name_field.value == "Jane"
    assert first_name_field.is_custom is False
    assert first_name_field.required is True

    email_field = next(f for f in form.fields if f.name == "email")
    assert email_field.value == "jane@example.com"

    custom_field = next(f for f in form.fields if f.name == "custom_why")
    assert custom_field.is_custom is True
    assert custom_field.label == "Why this role?"


@respx.mock
def test_discover_form_raises_when_no_form_present():
    respx.get("https://example.com/apply").mock(
        return_value=httpx.Response(200, text="<html><body>no form</body></html>")
    )
    with pytest.raises(ATSAdapterError):
        _TestAdapter().discover_form("https://example.com/apply", _profile(), email="jane@example.com")


@respx.mock
def test_discover_form_raises_on_http_error():
    respx.get("https://example.com/apply").mock(return_value=httpx.Response(404))
    with pytest.raises(ATSAdapterError):
        _TestAdapter().discover_form("https://example.com/apply", _profile(), email="jane@example.com")


@respx.mock
def test_submit_posts_hidden_and_filled_fields():
    route = respx.post("https://example.com/submit").mock(return_value=httpx.Response(200))

    filled = DiscoveredForm(
        submit_url="https://example.com/submit",
        hidden_fields={"csrf_token": "tok-abc"},
        fields=[
            FormField(name="first_name", label="First name", field_type="text", required=True, value="Jane"),
            FormField(
                name="custom_why", label="Why this role?", field_type="textarea", required=False,
                value="", is_custom=True,
            ),
        ],
    )

    _TestAdapter().submit(filled, cv_pdf=b"%PDF-cv", lettre_pdf=b"%PDF-lettre")

    assert route.called
    sent_body = route.calls[0].request.content
    assert b"tok-abc" in sent_body
    assert b"Jane" in sent_body


@respx.mock
def test_submit_raises_on_http_error():
    respx.post("https://example.com/submit").mock(return_value=httpx.Response(500))
    filled = DiscoveredForm(submit_url="https://example.com/submit", hidden_fields={}, fields=[])

    with pytest.raises(ATSAdapterError):
        _TestAdapter().submit(filled, cv_pdf=b"%PDF", lettre_pdf=b"%PDF")
