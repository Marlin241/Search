import html
from urllib.parse import urlsplit

import httpx

from app.config import get_settings
from app.job_search.schemas import JobListing

_RESEND_API_URL = "https://api.resend.com/emails"
_ALLOWED_URL_SCHEMES = {"http", "https"}


class EmailSendError(Exception):
    pass


def _safe_href(url: str) -> str:
    """Only http(s) URLs are ever linked - rejects `javascript:` and other
    executable schemes a compromised/malicious upstream job listing could
    smuggle in. HTML-escaping alone (see _render_html) does not stop this,
    since the scheme itself contains no special HTML characters to escape."""
    if urlsplit(url).scheme not in _ALLOWED_URL_SCHEMES:
        return "#"
    return html.escape(url)


def _render_html(listings: list[JobListing], unsubscribe_url: str) -> str:
    # Every field interpolated here (title/company/location, all from
    # external job-search APIs we don't control) is HTML-escaped - without
    # it, a listing whose title/company contained raw HTML would be
    # rendered as-is in the recipient's email client.
    items = "".join(
        f'<li><a href="{_safe_href(listing.url)}">{html.escape(listing.title)}</a>'
        f" — {html.escape(listing.company)}"
        f"{f' ({html.escape(listing.location)})' if listing.location else ''}</li>"
        for listing in listings
    )
    return (
        "<p>Nouvelles offres correspondant à votre recherche :</p>"
        f"<ul>{items}</ul>"
        f'<p><a href="{_safe_href(unsubscribe_url)}">Se désabonner de ces alertes</a></p>'
    )


def send_daily_digest_email(
    to_email: str, listings: list[JobListing], unsubscribe_token: str
) -> None:
    settings = get_settings()
    count = len(listings)
    subject = (
        f"{count} nouvelle{'s' if count > 1 else ''} offre{'s' if count > 1 else ''} "
        "correspondant à votre recherche"
    )
    unsubscribe_url = (
        f"{settings.backend_base_url}/job-search/saved-search/unsubscribe"
        f"?token={unsubscribe_token}"
    )
    response = httpx.post(
        _RESEND_API_URL,
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        json={
            "from": settings.resend_from_email,
            "to": [to_email],
            "subject": subject,
            "html": _render_html(listings, unsubscribe_url),
        },
        timeout=10.0,
    )
    if response.status_code >= 400:
        raise EmailSendError(
            f"Échec de l'envoi de l'email via Resend ({response.status_code}): {response.text}"
        )
