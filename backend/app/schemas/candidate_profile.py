import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# Champs texte libres (nom, intitulés de poste...) : jamais de balises HTML/JS
# stockées telles quelles - défense en profondeur contre l'injection de
# prompt (ces valeurs finissent dans des prompts LLM) et l'affichage cassé.
_TAG_RE = re.compile(r"<[^>]*>")

# Permissif à dessein (formats internationaux, espaces, tirets, parenthèses) :
# le but est de rejeter le "pas-un-numero-!!!", pas d'imposer un format
# régional précis.
_PHONE_RE = re.compile(r"^[0-9+ ().-]{6,30}$")

_URL_RE = re.compile(r"^https?://[^\s/]+\.[^\s]+$", re.IGNORECASE)

# Devises supportées pour l'attente salariale du candidat - un allow-list
# volontairement restreint (pas la liste ISO 4217 complète) : ce sont les
# seuls marchés réellement en jeu aujourd'hui. XOF (Afrique de l'Ouest,
# BCEAO) et XAF (Afrique centrale, BEAC) sont deux devises distinctes bien
# que toutes deux appelées "FCFA" dans le langage courant.
_SUPPORTED_CURRENCIES = {"XOF", "XAF", "EUR", "USD"}


def _strip_tags(value: str) -> str:
    return _TAG_RE.sub("", value).strip()


def _clean_list(values: list[str], max_len: int = 100) -> list[str]:
    cleaned = []
    for value in values:
        value = _strip_tags(value)[:max_len]
        if value:
            cleaned.append(value)
    return cleaned


def _validate_url(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if not _URL_RE.match(value):
        raise ValueError(
            "L'URL doit être complète et commencer par http:// ou https://."
        )
    return value


class CandidateProfileIn(BaseModel):
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    phone: str = Field(max_length=30)
    address: str | None = Field(default=None, max_length=255)
    linkedin_url: str | None = Field(default=None, max_length=500)
    portfolio_url: str | None = Field(default=None, max_length=500)
    work_authorization: str = Field(max_length=255)
    salary_expectation: str | None = Field(default=None, max_length=100)

    @field_validator("first_name", "last_name", "work_authorization")
    @classmethod
    def _clean_text(cls, value: str) -> str:
        return _strip_tags(value)

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, value: str) -> str:
        value = value.strip()
        if value and not _PHONE_RE.match(value):
            raise ValueError(
                "Numéro de téléphone invalide (chiffres, espaces, +, - et () uniquement)."
            )
        return value

    @field_validator("linkedin_url", "portfolio_url")
    @classmethod
    def _validate_url_field(cls, value: str | None) -> str | None:
        return _validate_url(value)


class CandidateProfileOut(BaseModel):
    first_name: str
    last_name: str
    full_name: str
    phone: str
    address: str | None
    linkedin_url: str | None
    portfolio_url: str | None
    work_authorization: str
    salary_expectation: str | None
    cv_filename: str | None
    has_cv: bool
    updated_at: datetime
    desired_job_titles: list[str] | None
    seniority_level: str | None
    desired_locations: list[str] | None
    remote_preference: bool
    contract_types: list[str] | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    weekly_application_goal: int | None
    has_profile_photo: bool


class OnboardingProfileIn(BaseModel):
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    desired_job_titles: list[str] = Field(default_factory=list, max_length=20)
    seniority_level: str | None = Field(default=None, max_length=50)
    desired_locations: list[str] = Field(default_factory=list, max_length=20)
    remote_preference: bool = False
    contract_types: list[str] = Field(default_factory=list, max_length=10)
    salary_min: int | None = Field(default=None, ge=0, le=100_000_000)
    salary_max: int | None = Field(default=None, ge=0, le=100_000_000)
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3)
    weekly_application_goal: int | None = Field(default=None, ge=0, le=1000)

    @field_validator("first_name", "last_name")
    @classmethod
    def _clean_text(cls, value: str) -> str:
        return _strip_tags(value)

    @field_validator("desired_job_titles", "desired_locations", "contract_types")
    @classmethod
    def _clean_str_list(cls, values: list[str]) -> list[str]:
        return _clean_list(values)

    @field_validator("salary_currency")
    @classmethod
    def _validate_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if value not in _SUPPORTED_CURRENCIES:
            raise ValueError(f"Devise non supportée : {value}.")
        return value


class ExtractedPhotoOut(BaseModel):
    key: str
    preview_url: str
