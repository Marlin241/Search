import re

from app.personalization.schemas import RewrittenCv

# Non-capturing groups so `.findall()` returns whole matches, not sub-groups.
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
# NOTE: word separators are restricted to spaces/tabs (not `\s`, which also
# matches newlines). CV text and the joined rewritten fields are newline
# delimited between unrelated fields/lines (e.g. job title vs. company, or
# one CV section vs. the next); with a bare `\s+` the regex would happily
# bleed across those line breaks and fuse unrelated capitalized words (e.g.
# a title's last word + the next line's employer name) into a single bogus
# "proper noun" phrase that can never match between original and rewritten
# text. Restricting to `[ \t]+` keeps matches within one logical line/field.
_PROPER_NOUN_RE = re.compile(
    r"\b[A-ZÀ-Ý][\wÀ-ÿ'&.-]*(?:[ \t]+[A-ZÀ-Ý][\wÀ-ÿ'&.-]*){1,3}\b"
)


def _extract_reference_terms(text: str) -> set[str]:
    years = set(_YEAR_RE.findall(text))
    proper_nouns = {match.strip().lower() for match in _PROPER_NOUN_RE.findall(text)}
    return years | proper_nouns


def cv_needs_review(original_cv_text: str, rewritten: RewrittenCv) -> bool:
    """Lightweight, deterministic anti-hallucination guard for a rewritten CV.

    Compares 4-digit years and multi-word capitalized phrases (a cheap proxy
    for employer names, school names, and dates - the most damaging things
    to hallucinate) between the original CV text and the rewritten CV. If
    the rewritten CV mentions one that isn't in the original, it's flagged
    for the user to double-check. This never blocks generation - it only
    sets a flag - and it deliberately does not call a second LLM to verify,
    per the design spec.
    """
    original_terms = _extract_reference_terms(original_cv_text)

    # Fields (and each bullet) are joined with newlines, not spaces, so an
    # entry's title, company, dates, and each bullet each stay on their own
    # "line" for the proper-noun regex above - otherwise e.g. a title ending
    # in a capitalized word immediately followed by a capitalized company
    # name (or one bullet's last word fused with the next bullet's first)
    # would be read as one bogus phrase instead of separately-comparable
    # terms.
    rewritten_text = "\n".join(
        [
            rewritten.summary,
            *(
                f"{entry.title}\n{entry.company}\n{entry.dates}\n{'\n'.join(entry.bullets)}"
                for entry in rewritten.experience
            ),
            *rewritten.education,
            *rewritten.skills,
        ]
    )
    rewritten_terms = _extract_reference_terms(rewritten_text)

    return not rewritten_terms.issubset(original_terms)
