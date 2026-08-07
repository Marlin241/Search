from app.ats_adapters.base import HtmlFormAdapter


class GreenhouseAdapter(HtmlFormAdapter):
    standard_field_aliases = {
        "first_name": ["first_name"],
        "last_name": ["last_name"],
        "email": ["email"],
        "phone": ["phone"],
        "linkedin": ["linkedin"],
        "portfolio": ["website", "portfolio"],
    }
    resume_field_names = ["job_application[resume]"]
    cover_letter_field_names = ["job_application[cover_letter]"]
