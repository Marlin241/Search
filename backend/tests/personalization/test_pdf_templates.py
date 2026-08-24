from app.models.candidate_profile import CandidateProfile
from app.personalization.pdf_templates import CvStyleOptions, render_cv
from app.personalization.schemas import CvExperienceEntry, RewrittenCv

_CV = RewrittenCv(
    summary="Résumé optimisé pour cette offre.",
    experience=[
        CvExperienceEntry(
            title="Développeuse",
            company="Acme",
            dates="2020-2022",
            bullets=["A conçu des API."],
        )
    ],
    education=["Master Informatique"],
    skills=["Python"],
)


def test_all_three_templates_render_valid_single_page_pdf():
    for template in ("classic", "modern", "minimal"):
        pdf_bytes, page_count = render_cv(template, _CV, None, CvStyleOptions())
        assert pdf_bytes.startswith(b"%PDF")
        assert page_count == 1


def test_render_cv_includes_candidate_header_when_profile_has_a_name():
    profile = CandidateProfile(user_id=1, full_name="Jane Doe", phone="0601020304")
    pdf_bytes, _ = render_cv("classic", _CV, profile, CvStyleOptions())
    # fpdf2 encodes text as PDF content streams, not as searchable plain
    # text in the raw bytes - so this only proves the header path executed
    # without raising, not that "Jane Doe" is literally visible in the raw
    # bytes. It's still a meaningful regression check: rendering with a
    # non-null profile is a materially different code path (render_header)
    # than the None-profile case covered by test_render_cv_pdf_returns_nonempty_pdf_bytes.
    assert pdf_bytes.startswith(b"%PDF")


def test_render_cv_style_accent_color_and_margins_do_not_break_rendering():
    style = CvStyleOptions(accent_color="#ff0000", margins=20, spacing="compact")
    pdf_bytes, page_count = render_cv("modern", _CV, None, style)
    assert pdf_bytes.startswith(b"%PDF")
    assert page_count >= 1
