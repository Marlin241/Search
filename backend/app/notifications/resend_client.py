import html
from urllib.parse import urlsplit

import httpx

from app.config import get_settings
from app.job_search.schemas import JobListing
from app.models.application import Application

_RESEND_API_URL = "https://api.resend.com/emails"
_ALLOWED_URL_SCHEMES = {"http", "https"}


class EmailSendError(Exception):
    pass


def _safe_href(url: str) -> str:
    """Only http(s) URLs are ever linked - rejects `javascript:` and other
    executable schemes a compromised/malicious upstream source could
    smuggle in. HTML-escaping alone does not stop this, since the scheme
    itself contains no special HTML characters to escape."""
    if urlsplit(url).scheme not in _ALLOWED_URL_SCHEMES:
        return "#"
    return html.escape(url)


def _send_email(to_email: str, subject: str, html_body: str) -> None:
    settings = get_settings()
    response = httpx.post(
        _RESEND_API_URL,
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        json={
            "from": settings.resend_from_email,
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        },
        timeout=10.0,
    )
    if response.status_code >= 400:
        raise EmailSendError(
            f"Échec de l'envoi de l'email via Resend ({response.status_code}): {response.text}"
        )


def send_feedback_notification(
    admin_email: str, from_user: str, page: str, message: str
) -> None:
    """Notify the admin of a new in-app feedback. No-op when no admin email
    is configured (dev / not yet set up)."""
    if not admin_email:
        return
    body = (
        f"<p><strong>De :</strong> {html.escape(from_user)}</p>"
        f"<p><strong>Page :</strong> {html.escape(page)}</p>"
        f"<p>{html.escape(message)}</p>"
    )
    _send_email(admin_email, "Nouveau retour beta", body)


def send_access_request_notification(
    admin_email: str, from_email: str, note: str
) -> None:
    """Notify the admin of a new beta access request from the landing page.
    No-op when no admin email is configured."""
    if not admin_email:
        return
    body = (
        f"<p><strong>Email :</strong> {html.escape(from_email)}</p>"
        f"<p><strong>Message :</strong></p>"
        f"<p>{html.escape(note) or '<em>(vide)</em>'}</p>"
    )
    _send_email(admin_email, "Nouvelle demande d'accès à la beta", body)


def send_password_reset_email(to_email: str, reset_url: str) -> None:
    safe = _safe_href(reset_url)
    html_body = (
        "<p>Tu as demandé à réinitialiser ton mot de passe.</p>"
        f'<p><a href="{safe}">Choisir un nouveau mot de passe</a></p>'
        "<p>Ce lien expire dans 1 heure. Si tu n'es pas à l'origine de "
        "cette demande, ignore cet email.</p>"
    )
    _send_email(to_email, "Réinitialisation de ton mot de passe", html_body)


def _render_job_listings_html(listings: list[JobListing], unsubscribe_url: str) -> str:
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
    _send_email(to_email, subject, _render_job_listings_html(listings, unsubscribe_url))


def _render_application_reminders_html(
    to_relance: list[Application],
    to_finalize: list[Application],
    candidatures_url: str,
) -> str:
    # company_name/job_title are, like a JobListing's fields, ultimately
    # sourced from external APIs or free-form user input - HTML-escaped for
    # the same reason as _render_job_listings_html above.
    sections = []
    if to_relance:
        items = []
        for application in to_relance:
            assert (
                application.submitted_at is not None
            )  # to_relance is filtered on submitted_at <= cutoff
            items.append(
                f"<li>{html.escape(application.job_title)} — "
                f"{html.escape(application.company_name)} "
                f"(envoyée le {application.submitted_at.strftime('%d/%m/%Y')})</li>"
            )
        sections.append(
            "<p>Candidatures à relancer (envoyées, sans réponse) :</p>"
            f"<ul>{''.join(items)}</ul>"
        )
    if to_finalize:
        items = [
            f"<li>{html.escape(application.job_title)} — "
            f"{html.escape(application.company_name)} "
            f"(créée le {application.created_at.strftime('%d/%m/%Y')})</li>"
            for application in to_finalize
        ]
        sections.append(
            "<p>Candidatures à finaliser (jamais envoyées) :</p>"
            f"<ul>{''.join(items)}</ul>"
        )
    sections.append(
        f'<p><a href="{_safe_href(candidatures_url)}">Voir mes candidatures</a></p>'
    )
    return "".join(sections)


def send_application_reminders_email(
    to_email: str, to_relance: list[Application], to_finalize: list[Application]
) -> None:
    settings = get_settings()
    count = len(to_relance) + len(to_finalize)
    subject = f"{count} candidature{'s' if count > 1 else ''} à relancer ou finaliser"
    candidatures_url = f"{settings.frontend_base_url}/candidatures"
    _send_email(
        to_email,
        subject,
        _render_application_reminders_html(to_relance, to_finalize, candidatures_url),
    )
