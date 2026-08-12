import unicodedata

# Small bilingual synonym table for common job-title vocabulary. Greenhouse
# and Lever boards for non-French companies (e.g. Wave, see seed_companies.py)
# are posted in English, so a literal substring match against a French
# keyword like "développeur" would silently exclude every one of their
# listings even though "Software Engineer" is exactly that job.
_SYNONYMS: dict[str, tuple[str, ...]] = {
    "developpeur": ("developer", "engineer", "dev"),
    "developpeuse": ("developer", "engineer", "dev"),
    "ingenieur": ("engineer",),
    "ingenieure": ("engineer",),
    "analyste": ("analyst",),
    "comptable": ("accountant",),
    "commercial": ("sales",),
    "commerciale": ("sales",),
    "responsable": ("manager", "lead"),
    "gestionnaire": ("manager", "officer"),
    "juriste": ("legal counsel", "legal"),
    "recruteur": ("recruiter",),
    "recruteuse": ("recruiter",),
    "controleur": ("controller",),
    "controleuse": ("controller",),
    "auditeur": ("auditor",),
    "auditrice": ("auditor",),
    "ressources humaines": ("human resources", "hr", "people"),
}


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def keyword_matches_title(keyword: str, title: str) -> bool:
    """True if `keyword` matches `title`, either as a direct (accent- and
    case-insensitive) substring or via a known French/English job-title
    synonym, e.g. "développeur" matching "Software Engineer"."""
    if not keyword:
        return True
    normalized_title = _strip_accents(title.lower())
    normalized_keyword = _strip_accents(keyword.strip().lower())
    if normalized_keyword in normalized_title:
        return True
    return any(synonym in normalized_title for synonym in _SYNONYMS.get(normalized_keyword, ()))
