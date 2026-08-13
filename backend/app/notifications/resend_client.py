import httpx

from app.config import get_settings
from app.job_search.schemas import JobListing

_RESEND_API_URL = "https://api.resend.com/emails"


class EmailSendError(Exception):
    pass


def _render_html(listings: list[JobListing], unsubscribe_url: str) -> str:
    items = "".join(
        f'<li><a href="{listing.url}">{listing.title}</a> — {listing.company}'
        f"{f' ({listing.location})' if listing.location else ''}</li>"
        for listing in listings
    )
    return (
        "<p>Nouvelles offres correspondant à votre recherche :</p>"
        f"<ul>{items}</ul>"
        f'<p><a href="{unsubscribe_url}">Se désabonner de ces alertes</a></p>'
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
