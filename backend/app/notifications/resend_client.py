import html

import httpx

from app.config import get_settings
from app.job_search.schemas import JobListing
from app.models.application import Application
from app.notifications.email_layout import (
    BRAND_NAME,
    html_to_text,
    render_email,
    safe_href,
)

_RESEND_API_URL = "https://api.resend.com/emails"

# Conservé pour les appelants internes de ce module.
_safe_href = safe_href


class EmailSendError(Exception):
    pass


def _from_field(from_email: str) -> str:
    """Ajoute un nom d'expéditeur lisible ("Search <alertes@…>") — un `from`
    nu passe plus facilement en spam. Respecte une valeur déjà formatée."""
    return from_email if "<" in from_email else f"{BRAND_NAME} <{from_email}>"


def _send_email(
    to_email: str,
    subject: str,
    html_body: str,
    *,
    extra_headers: dict[str, str] | None = None,
) -> None:
    settings = get_settings()
    if not settings.resend_api_key:
        # Resend non configuré (dev / CI) → l'envoi d'email est un no-op.
        # Évite un POST voué à l'échec et un header "Bearer " illégal.
        return
    payload: dict[str, object] = {
        "from": _from_field(settings.resend_from_email),
        "to": [to_email],
        "subject": subject,
        "html": html_body,
        # Version texte dérivée du HTML : un email HTML-only sans part texte
        # est un signal négatif de plus pour les filtres anti-spam.
        "text": html_to_text(html_body),
    }
    if extra_headers:
        payload["headers"] = extra_headers
    response = httpx.post(
        _RESEND_API_URL,
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        json=payload,
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
    escaped_note = html.escape(note) or "<em>(vide)</em>"
    body = render_email(
        heading="Nouvelle demande d'accès",
        paragraphs=[
            f"<strong>Email :</strong> {html.escape(from_email)}",
            f"<strong>Message :</strong><br>{escaped_note}",
            "À traiter dans <em>Admin ▸ Demandes d'accès</em>.",
        ],
        context_line="Notification interne — nouvelle demande d'accès à la beta.",
        preheader=from_email,
    )
    _send_email(admin_email, "Nouvelle demande d'accès à la beta", body)


def send_access_request_confirmation(to_email: str) -> None:
    """Accusé de réception envoyé au demandeur juste après le dépôt du
    formulaire « Demander un accès » de la landing publique."""
    body = render_email(
        heading="Demande bien reçue",
        paragraphs=[
            "Salut,",
            (
                f"On a bien reçu ta demande d'accès à la beta de "
                f"<strong>{BRAND_NAME}</strong> — l'outil qui t'aide à décrocher "
                f"ton job : diagnostic ATS de ton CV, réécriture ciblée, lettre "
                f"de motivation et préparation d'entretien par IA, offres locales."
            ),
            (
                "La beta est sur invitation et les places sont limitées. On "
                "revient vers toi par email dès qu'une place se libère."
            ),
            "— L'équipe Yokkute Labs",
        ],
        context_line=(
            f"Tu reçois cet email parce que tu as demandé un accès à la beta "
            f"de {BRAND_NAME}."
        ),
        preheader="On revient vers toi dès qu'une place se libère.",
    )
    _send_email(to_email, "On a bien reçu ta demande d'accès", body)


def send_access_granted_email(to_email: str, invite_code: str, login_url: str) -> None:
    """Envoi du code d'invitation au demandeur quand l'admin approuve sa
    demande d'accès."""
    body = render_email(
        heading="Ton accès à la beta est ouvert",
        paragraphs=[
            "Bonne nouvelle — une place s'est libérée pour toi.",
            "Ton code d'invitation à usage unique :",
            (
                '<span style="display:inline-block;padding:8px 14px;'
                "border-radius:8px;background:#f1f0fb;font-family:ui-monospace,"
                "SFMono-Regular,Menlo,monospace;font-size:16px;font-weight:600;"
                'letter-spacing:0.04em;color:#1e1b2e;">'
                f"{html.escape(invite_code)}</span>"
            ),
            (
                "Clique sur le bouton, va sur l'onglet « Inscription » et colle "
                "le code. Il expire dans 30 jours."
            ),
        ],
        cta=("Créer mon compte", login_url),
        context_line=(
            f"Tu reçois cet email parce que ta demande d'accès à la beta de "
            f"{BRAND_NAME} a été acceptée."
        ),
        preheader=f"Ton code : {invite_code}",
    )
    _send_email(to_email, "Ton accès à la beta est ouvert", body)


def send_password_reset_email(to_email: str, reset_url: str) -> None:
    body = render_email(
        heading="Réinitialisation de ton mot de passe",
        paragraphs=[
            (
                "Tu as demandé à réinitialiser ton mot de passe. Clique sur le "
                "bouton ci-dessous pour en choisir un nouveau."
            ),
            (
                "Ce lien expire dans 1 heure. Si tu n'es pas à l'origine de "
                "cette demande, ignore cet email — rien ne change."
            ),
        ],
        cta=("Choisir un nouveau mot de passe", reset_url),
        context_line=(
            f"Tu reçois cet email parce qu'une réinitialisation de mot de passe "
            f"a été demandée pour ton compte {BRAND_NAME}."
        ),
        preheader="Lien valable 1 heure.",
    )
    _send_email(to_email, "Réinitialisation de ton mot de passe", body)


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
    _send_email(
        to_email,
        subject,
        _render_job_listings_html(listings, unsubscribe_url),
        # Désabonnement en un clic (RFC 8058) : Gmail/Yahoo/Outlook affichent
        # un bouton "Se désabonner" dans leur UI qui POST directement cette
        # URL, sans jamais ouvrir l'app - un mail récurrent qui ne l'a pas
        # est traité comme moins fiable par les filtres anti-spam. La route
        # POST correspondante est définie à côté du GET dans job_search.py.
        extra_headers={
            "List-Unsubscribe": f"<{unsubscribe_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    )


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
