import json
from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.job_search.schemas import JobListing
from app.models.application import Application
from app.notifications.resend_client import (
    EmailSendError,
    send_application_reminders_email,
    send_daily_digest_email,
)


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


@respx.mock
def test_send_daily_digest_email_escapes_html_in_listing_fields():
    route = respx.post("https://api.resend.com/emails").mock(
        return_value=httpx.Response(200, json={"id": "abc"})
    )

    malicious = JobListing(
        title="<script>alert(1)</script>",
        company="Acme & Co <img src=x onerror=alert(1)>",
        location='Paris" onmouseover="alert(1)',
        snippet="...",
        url="https://example.com/job/1",
        source="france_travail",
        ats_type=None,
    )

    send_daily_digest_email("jane@example.com", [malicious], "tok-123")

    payload = json.loads(route.calls[0].request.content)
    # The real security property: no unescaped tag delimiter reaches the
    # output, so no HTML element can actually form - not the absence of
    # any particular harmless substring like the word "onerror=" as inert
    # text (which is fine to keep, since it can no longer execute).
    assert "<script>" not in payload["html"]
    assert "&lt;script&gt;" in payload["html"]
    assert "<img" not in payload["html"]
    assert "&lt;img" in payload["html"]


@respx.mock
def test_send_daily_digest_email_rejects_javascript_scheme_urls():
    route = respx.post("https://api.resend.com/emails").mock(
        return_value=httpx.Response(200, json={"id": "abc"})
    )

    send_daily_digest_email(
        "jane@example.com", [_listing("javascript:alert(1)")], "tok-123"
    )

    payload = json.loads(route.calls[0].request.content)
    assert "javascript:" not in payload["html"]


def _application(
    company_name: str = "Acme",
    job_title: str = "Développeur Python",
    submitted_at: datetime | None = None,
    created_at: datetime | None = None,
) -> Application:
    return Application(
        id=1,
        user_id=1,
        diagnostic_id=1,
        offer_url="https://example.com/job/1",
        source="manual",
        company_name=company_name,
        job_title=job_title,
        ats_type=None,
        status="soumise_auto",
        submitted_at=submitted_at,
        created_at=created_at or datetime(2026, 7, 1, tzinfo=UTC).replace(tzinfo=None),
    )


@respx.mock
def test_send_application_reminders_email_posts_to_resend():
    route = respx.post("https://api.resend.com/emails").mock(
        return_value=httpx.Response(200, json={"id": "abc"})
    )

    to_relance = [
        _application(submitted_at=datetime(2026, 7, 1, tzinfo=UTC).replace(tzinfo=None))
    ]
    to_finalize: list[Application] = []

    send_application_reminders_email("jane@example.com", to_relance, to_finalize)

    assert route.called
    payload = json.loads(route.calls[0].request.content)
    assert payload["to"] == ["jane@example.com"]
    assert "1 candidature" in payload["subject"]
    assert "à relancer" in payload["subject"]
    assert "Acme" in payload["html"]
    assert "candidatures" in payload["html"]  # lien vers la page candidatures


@respx.mock
def test_send_application_reminders_email_includes_both_sections():
    route = respx.post("https://api.resend.com/emails").mock(
        return_value=httpx.Response(200, json={"id": "abc"})
    )

    to_relance = [
        _application(
            company_name="Acme",
            submitted_at=datetime(2026, 7, 1, tzinfo=UTC).replace(tzinfo=None),
        )
    ]
    to_finalize = [_application(company_name="Globex")]

    send_application_reminders_email("jane@example.com", to_relance, to_finalize)

    payload = json.loads(route.calls[0].request.content)
    assert "2 candidatures" in payload["subject"]
    assert "Acme" in payload["html"]
    assert "Globex" in payload["html"]


@respx.mock
def test_send_application_reminders_email_raises_on_http_error():
    respx.post("https://api.resend.com/emails").mock(
        return_value=httpx.Response(422, json={"message": "invalid from address"})
    )

    with pytest.raises(EmailSendError):
        send_application_reminders_email(
            "jane@example.com",
            [
                _application(
                    submitted_at=datetime(2026, 7, 1, tzinfo=UTC).replace(tzinfo=None)
                )
            ],
            [],
        )


@respx.mock
def test_send_application_reminders_email_escapes_html_in_fields():
    route = respx.post("https://api.resend.com/emails").mock(
        return_value=httpx.Response(200, json={"id": "abc"})
    )

    to_finalize = [
        _application(company_name="<script>alert(1)</script>", job_title="Dev")
    ]

    send_application_reminders_email("jane@example.com", [], to_finalize)

    payload = json.loads(route.calls[0].request.content)
    assert "<script>" not in payload["html"]
    assert "&lt;script&gt;" in payload["html"]
