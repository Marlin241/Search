"""Gabarit HTML de marque partagé par les emails transactionnels.

Contraintes email : styles inline uniquement, layout en tables, pas de
flex/grid, largeur ~600px, les polices web ne chargent pas (fallback
système). Le nom produit reste "Search" (provisoire, cf. lib/brand.ts)."""

import html
from urllib.parse import urlsplit

_ALLOWED_URL_SCHEMES = {"http", "https"}


def safe_href(url: str) -> str:
    """N'autorise que les URL http(s) — neutralise `javascript:` et autres
    schémas exécutables qu'une source amont compromise pourrait glisser.
    L'échappement HTML seul n'y suffit pas (le schéma ne contient aucun
    caractère spécial HTML)."""
    if urlsplit(url).scheme not in _ALLOWED_URL_SCHEMES:
        return "#"
    return html.escape(url)


BRAND_NAME = "Search"
PARENT_NAME = "Yokkute Labs"
PARENT_URL = "https://yokkutelabs.com"
# Marque (l'arche + la flèche montante) en PNG transparent, encodée en
# base64 et inlinée dans le HTML — une <img src> distante était bloquée par
# défaut par la plupart des clients mail (premier contact = pas encore dans
# les "expéditeurs sûrs"), ce qui laissait juste le carré indigo vide sans
# le tracé blanc dessus. En data URI, rien à charger : ça s'affiche même
# images désactivées. Généré depuis le même tracé que
# frontend/components/common/LogoMark.tsx ; régénérer avec :
#   python3 -c "import base64; print(base64.b64encode(open(
#   'frontend/public/brand/logo-mark-email.png','rb').read()).decode())"
_LOGO_MARK_DATA_URI = (
    "data:image/png;base64,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"
    "0AAAAASUVORK5CYII="
)

_PRIMARY = "#4f46e5"  # indigo — cohérent avec le design system du produit
_INK = "#1e1b2e"
_MUTED = "#6b7280"
_BG = "#f4f4f7"
_CARD = "#ffffff"
_BORDER = "#e6e6ef"
_FONT = (
    "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,"
    "'Apple Color Emoji','Segoe UI Emoji',sans-serif"
)


def _wordmark() -> str:
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0">'
        f"<tr>"
        f'<td style="background:{_PRIMARY};border-radius:8px;width:34px;'
        f'height:34px;text-align:center;vertical-align:middle;">'
        f'<img src="{_LOGO_MARK_DATA_URI}" width="18" height="18" alt="" '
        f'style="display:block;margin:0 auto;border:0;outline:none;" /></td>'
        f'<td style="padding-left:10px;font-family:{_FONT};font-size:19px;'
        f'font-weight:700;color:{_INK};letter-spacing:-0.01em;">'
        f"{BRAND_NAME}</td>"
        f"</tr></table>"
    )


def _button(label: str, href: str) -> str:
    safe = safe_href(href)
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        f'style="margin:24px 0;"><tr>'
        f'<td style="background:{_PRIMARY};border-radius:8px;">'
        f'<a href="{safe}" style="display:inline-block;padding:12px 24px;'
        f"font-family:{_FONT};font-size:15px;font-weight:600;color:#ffffff;"
        f'text-decoration:none;">{html.escape(label)}</a>'
        f"</td></tr></table>"
    )


def render_email(
    *,
    heading: str,
    paragraphs: list[str],
    cta: tuple[str, str] | None = None,
    context_line: str,
    preheader: str = "",
) -> str:
    """`heading` et `context_line` sont échappés ; `paragraphs` est du HTML
    déjà sûr (les appelants n'y injectent que des libellés maîtrisés ou des
    valeurs passées par `html.escape`). `cta` = (label, href)."""
    blocks = "".join(
        f'<p style="margin:0 0 16px;font-family:{_FONT};font-size:15px;'
        f'line-height:1.6;color:{_INK};">{p}</p>'
        for p in paragraphs
    )
    button = _button(*cta) if cta else ""
    hidden_preheader = (
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;">'
        f"{html.escape(preheader)}</div>"
        if preheader
        else ""
    )
    return (
        '<!doctype html><html lang="fr"><head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light">'
        f"<title>{html.escape(heading)}</title></head>"
        f'<body style="margin:0;padding:0;background:{_BG};">'
        f"{hidden_preheader}"
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'border="0" style="background:{_BG};padding:32px 12px;"><tr><td align="center">'
        f'<table role="presentation" width="600" cellpadding="0" cellspacing="0" '
        f'border="0" style="width:600px;max-width:100%;">'
        # header
        f'<tr><td style="padding:0 8px 20px;">{_wordmark()}</td></tr>'
        # card
        f'<tr><td style="background:{_CARD};border:1px solid {_BORDER};'
        f'border-radius:14px;padding:32px;">'
        f'<h1 style="margin:0 0 20px;font-family:{_FONT};font-size:20px;'
        f'font-weight:700;color:{_INK};">{html.escape(heading)}</h1>'
        f"{blocks}{button}"
        f"</td></tr>"
        # footer
        f'<tr><td style="padding:20px 8px 0;font-family:{_FONT};font-size:12px;'
        f'line-height:1.6;color:{_MUTED};">'
        f'<p style="margin:0 0 6px;">{html.escape(context_line)}</p>'
        f'<p style="margin:0;">{BRAND_NAME} — un produit '
        f'<a href="{PARENT_URL}" style="color:{_MUTED};">{PARENT_NAME}</a>. '
        "Le copilote IA pour ta recherche d’emploi, pensé pour Dakar "
        "et l’Afrique de l’Ouest.</p>"
        f"</td></tr>"
        f"</table></td></tr></table></body></html>"
    )
