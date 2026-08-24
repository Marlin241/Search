from typing import Literal

from app.models.candidate_profile import CandidateProfile
from app.personalization.pdf_templates import classic, minimal, modern
from app.personalization.pdf_templates.base import CvStyleOptions
from app.personalization.schemas import RewrittenCv

_RENDERERS = {
    "classic": classic.render,
    "modern": modern.render,
    "minimal": minimal.render,
}


def render_cv(
    template: Literal["classic", "modern", "minimal"],
    rewritten: RewrittenCv,
    profile: CandidateProfile | None,
    style: CvStyleOptions,
) -> tuple[bytes, int]:
    return _RENDERERS[template](rewritten, profile, style)


__all__ = ["CvStyleOptions", "render_cv"]
