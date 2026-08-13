import json

import httpx
import pytest
import respx

from app.job_search.schemas import JobListing
from app.notifications.resend_client import EmailSendError, send_daily_digest_email


def _listing(url: str = "https://example.com/job/1") -> JobListing:
    return JobListing(
        title="Développeur Python",
        company="Acme",
        location="Paris",
        snippet="...",
        url=url,
        source="france_travail",
        ats_type=None,
    )


@respx.mock
def test_send_daily_digest_email_posts_to_resend():
    route = respx.post("https://api.resend.com/emails").mock(
        return_value=httpx.Response(200, json={"id": "abc"})
    )

    send_daily_digest_email("jane@example.com", [_listing()], "tok-123")

    assert route.called
    request = route.calls[0].request
    assert request.headers["authorization"].startswith("Bearer ")
    payload = json.loads(request.content)
    assert payload["to"] == ["jane@example.com"]
    assert "1 nouvelle offre" in payload["subject"]
    assert "https://example.com/job/1" in payload["html"]
    assert "tok-123" in payload["html"]


@respx.mock
def test_send_daily_digest_email_raises_on_http_error():
    respx.post("https://api.resend.com/emails").mock(
        return_value=httpx.Response(422, json={"message": "invalid from address"})
    )

    with pytest.raises(EmailSendError):
        send_daily_digest_email("jane@example.com", [_listing()], "tok-123")


@respx.mock
def test_send_daily_digest_email_pluralizes_subject_for_multiple_listings():
    route = respx.post("https://api.resend.com/emails").mock(
        return_value=httpx.Response(200, json={"id": "abc"})
    )

    send_daily_digest_email(
        "jane@example.com",
        [_listing("https://example.com/job/1"), _listing("https://example.com/job/2")],
        "tok-123",
    )

    payload = json.loads(route.calls[0].request.content)
    assert "2 nouvelles offres" in payload["subject"]
