from typing import ClassVar
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from app.ats_adapters.errors import ATSAdapterError
from app.ats_adapters.schemas import DiscoveredForm, FormField
from app.models.candidate_profile import CandidateProfile
from app.offer_ingestion.scraper import ScrapingError, _validate_url


def _validate_url_for_ats(url: str) -> None:
    """Reuse offer_ingestion.scraper's SSRF validation (scheme allowlist +
    DNS-resolved private/internal address rejection), but re-raise as
    ATSAdapterError so callers of this module only ever see that error
    type, per its documented contract."""
    try:
        _validate_url(url)
    except ScrapingError as exc:
        raise ATSAdapterError(f"URL non autorisée: {exc}") from exc


class HtmlFormAdapter:
    """Generic adapter for ATS platforms (Greenhouse, Lever) that embed a
    single standard HTML application form on the offer's page.

    Subclasses set four class attributes to specialize this for their
    platform's field naming convention - no other code is platform-specific:

    - `standard_field_aliases`: maps a CandidateProfile concept
      ("first_name", "email", ...) to a list of substrings to match against
      the HTML field's `name` attribute (case-insensitive).
    - `resume_field_names` / `cover_letter_field_names`: the file input
      `name` attribute(s) the CV/lettre PDFs are attached under on submit.
    - `allowed_host_suffixes`: the domains this adapter is allowed to talk
      to (see `_validate_host_allowed`). Empty means unrestricted, which is
      only appropriate for the generic base class and its tests.
    """

    standard_field_aliases: dict[str, list[str]] = {}
    resume_field_names: list[str] = []
    cover_letter_field_names: list[str] = []
    allowed_host_suffixes: list[str] = []

    def __init__(self, http_client: httpx.Client | None = None):
        self._http = http_client or httpx.Client(timeout=15.0)

    def _validate_host_allowed(self, url: str) -> None:
        """Reject URLs whose host isn't on this adapter's platform allowlist.

        `ats_type` and `offer_url` are both unvalidated free-form client
        input, so without this a client could pair ats_type="greenhouse"
        with any URL and have the server fetch it - and then POST the user's
        CV and lettre to whatever form it found there. That target can be a
        perfectly public attacker-controlled host, which the SSRF check in
        `_validate_url_for_ats` (private/internal addresses only) does not
        and cannot cover; the two checks are complementary and both run.

        Matching is on a label boundary (exact host, or host ending in
        "." + suffix), not a bare string suffix, so a lookalike registrable
        domain such as "notgreenhouse.io" is rejected rather than accepted
        for merely ending in "greenhouse.io".
        """
        if not self.allowed_host_suffixes:
            return  # unrestricted: the generic base adapter and its tests
        host = (urlsplit(url).hostname or "").lower()
        for suffix in self.allowed_host_suffixes:
            normalized = suffix.lower().lstrip(".")
            if host == normalized or host.endswith(f".{normalized}"):
                return
        raise ATSAdapterError(
            f"URL non autorisée pour cette plateforme: '{host}' n'appartient pas à "
            f"{', '.join(self.allowed_host_suffixes)}."
        )

    def discover_form(self, offer_url: str, profile: CandidateProfile, email: str) -> DiscoveredForm:
        _validate_url_for_ats(offer_url)
        self._validate_host_allowed(offer_url)
        try:
            response = self._http.get(offer_url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ATSAdapterError(f"Impossible de charger le formulaire de candidature: {exc}") from exc

        soup = BeautifulSoup(response.text, "html.parser")
        form = soup.find("form")
        if form is None:
            raise ATSAdapterError("Aucun formulaire de candidature trouvé sur cette page.")

        action = form.get("action") or offer_url
        submit_url = urljoin(offer_url, action if isinstance(action, str) else offer_url)

        hidden_fields: dict[str, str] = {}
        fields: list[FormField] = []

        for tag in form.find_all(["input", "select", "textarea"]):
            name = tag.get("name")
            if not isinstance(name, str) or not name:
                continue
            tag_type_raw = tag.get("type", "text" if tag.name == "input" else tag.name)
            tag_type = tag_type_raw if isinstance(tag_type_raw, str) else "text"

            if tag_type == "hidden":
                value_raw = tag.get("value", "")
                hidden_fields[name] = value_raw if isinstance(value_raw, str) else ""
                continue
            if tag_type == "file":
                continue  # resume/cover letter - handled separately by submit()

            tag_id = tag.get("id")
            label_tag = form.find("label", attrs={"for": tag_id}) if isinstance(tag_id, str) and tag_id else None
            label = label_tag.get_text(strip=True) if label_tag else name

            options = [opt.get_text(strip=True) for opt in tag.find_all("option")] if tag.name == "select" else None

            value, is_standard = self._prefill_from_profile(name, profile, email)

            fields.append(
                FormField(
                    name=name,
                    label=label,
                    field_type=tag_type,
                    required=tag.has_attr("required"),
                    options=options,
                    value=value,
                    is_custom=not is_standard,
                )
            )

        return DiscoveredForm(submit_url=submit_url, fields=fields, hidden_fields=hidden_fields)

    def _prefill_from_profile(
        self, field_name: str, profile: CandidateProfile, email: str
    ) -> tuple[str | None, bool]:
        name_parts = profile.full_name.split() if profile.full_name else []
        profile_values = {
            "full_name": profile.full_name or None,
            "first_name": name_parts[0] if name_parts else None,
            "last_name": " ".join(name_parts[1:]) if len(name_parts) > 1 else None,
            "email": email,
            "phone": profile.phone or None,
            "address": profile.address,
            "linkedin": profile.linkedin_url,
            "portfolio": profile.portfolio_url,
        }
        lowered_field_name = field_name.lower()

        # Consider every (concept, alias) pair whose alias substring-matches
        # the field name AND whose concept actually has a fillable value -
        # a concept that matches but has no data (missing from
        # profile_values, or None there) must never count as a match, or
        # the field would end up blank (value=None) yet marked as
        # confidently filled (is_custom=False), hiding it from review.
        # Among the remaining candidates, prefer the most specific one (the
        # longest alias string) so a broad alias (e.g. "name") never
        # shadows a more specific one (e.g. "first_name") regardless of
        # declaration order in the subclass's alias table. Ties keep the
        # first-declared candidate.
        best_alias_len = -1
        best_value: str | None = None
        for concept, aliases in self.standard_field_aliases.items():
            value = profile_values.get(concept)
            if value is None:
                continue
            for alias in aliases:
                if alias in lowered_field_name and len(alias) > best_alias_len:
                    best_alias_len = len(alias)
                    best_value = value

        if best_alias_len == -1:
            return None, False
        return best_value, True

    def submit(self, filled_form: DiscoveredForm, cv_pdf: bytes, lettre_pdf: bytes) -> None:
        data = dict(filled_form.hidden_fields)
        for field in filled_form.fields:
            if field.value:
                data[field.name] = field.value

        files: dict[str, tuple[str, bytes, str]] = {}
        if self.resume_field_names:
            files[self.resume_field_names[0]] = ("cv.pdf", cv_pdf, "application/pdf")
        if self.cover_letter_field_names:
            files[self.cover_letter_field_names[0]] = ("lettre.pdf", lettre_pdf, "application/pdf")

        # The submit URL comes from the fetched page's <form action>, so it
        # is validated in its own right rather than trusted because the
        # offer URL passed.
        _validate_url_for_ats(filled_form.submit_url)
        self._validate_host_allowed(filled_form.submit_url)
        try:
            response = self._http.post(filled_form.submit_url, data=data, files=files)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ATSAdapterError(f"Échec de la soumission de la candidature: {exc}") from exc
