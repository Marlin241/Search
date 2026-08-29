"""Shared HTML-to-text for the job-search source adapters.

Several sources hand back a job description as an HTML fragment - and one
of them (Greenhouse) hands it back HTML-entity-encoded on top of that. This
is the single place that turns any of those into a clean one-line snippet.
"""

import html as html_module
import re

from bs4 import BeautifulSoup

_WHITESPACE_RE = re.compile(r"\s+")


def html_to_text(value: str | None) -> str:
    """Render an HTML fragment (optionally entity-encoded) down to a plain
    single-line string. Idempotent on text that is already plain."""
    text = BeautifulSoup(html_module.unescape(value or ""), "html.parser").get_text(
        separator=" "
    )
    return _WHITESPACE_RE.sub(" ", text).strip()
