from app.ats_adapters.base import HtmlFormAdapter


class LeverAdapter(HtmlFormAdapter):
    standard_field_aliases = {
        "full_name": ["name"],
        "email": ["email"],
        "phone": ["phone"],
        "linkedin": ["linkedin"],
        "portfolio": ["portfolio", "website"],
    }
    resume_field_names = ["resume"]
    cover_letter_field_names = ["coverLetter"]
    allowed_host_suffixes = ["lever.co"]
