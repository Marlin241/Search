from typing import ClassVar

from app.ats_adapters.base import HtmlFormAdapter


class LeverAdapter(HtmlFormAdapter):
    standard_field_aliases: ClassVar[dict[str, list[str]]] = {
        "full_name": ["name"],
        "email": ["email"],
        "phone": ["phone"],
        "linkedin": ["linkedin"],
        "portfolio": ["portfolio", "website"],
    }
    resume_field_names: ClassVar[list[str]] = ["resume"]
    cover_letter_field_names: ClassVar[list[str]] = ["coverLetter"]
    allowed_host_suffixes: ClassVar[list[str]] = ["lever.co"]
