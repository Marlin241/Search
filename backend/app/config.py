from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24
    anthropic_api_key: str
    cors_origins: list[str] = ["http://localhost:3000"]
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "personalization"
    france_travail_client_id: str = ""
    france_travail_client_secret: str = ""
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    adzuna_country: str = "fr"
    la_bonne_alternance_api_key: str = ""
    reliefweb_appname: str = "ats-diagnostic-search"
    reliefweb_countries: list[str] = [
        "Senegal",
        "Ivory Coast",
        "Cameroon",
        "Gabon",
        "Benin",
        "Togo",
        "Mali",
        "Burkina Faso",
        "Congo",
    ]
    ngojobs_feed_urls: list[str] = ["https://ngojobsinafrica.com/media-rss/"]
    weworkremotely_feed_urls: list[str] = ["https://weworkremotely.com/remote-jobs.rss"]
    enabled_crawlers: list[str] = ["emploi_dakar", "senjob", "educarriere_ci"]
    crawl_interval_hours: int = 3
    crawl_max_offers_per_site: int = 80
    crawl_request_delay_seconds: float = 1.0
    crawl_deactivate_after: int = 3
    crawl_suspicious_empty_threshold: int = 5
    crawler_contact_url: str = ""
    resend_api_key: str = ""
    resend_from_email: str = ""
    backend_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:3000"
    environment: str = "development"
    password_reset_token_ttl_minutes: int = 60
    glitchtip_dsn: str = ""
    admin_notify_email: str = ""
    # Emails (séparés par des virgules) promus admin automatiquement : au
    # démarrage pour les comptes existants, et à l'inscription — sans code
    # d'invitation, puisque le tout premier admin ne peut en recevoir de
    # personne. Promotion seule : retirer un email d'ici ne retire jamais
    # is_admin (une faute de frappe ne doit pas verrouiller dehors).
    admin_emails: str = ""

    llm_features_enabled: bool = True
    llm_monthly_quota_diagnostic: int = 7
    llm_monthly_quota_cv: int = 5
    llm_monthly_quota_lettre: int = 5
    llm_monthly_quota_compatibility: int = 13
    llm_monthly_quota_interview_prep: int = 3
    llm_monthly_quota_ats_prefill: int = 10

    @property
    def admin_email_set(self) -> set[str]:
        raw = self.admin_emails.replace(";", ",").replace(" ", ",")
        return {part.strip().lower() for part in raw.split(",") if part.strip()}

    @property
    def llm_monthly_quotas(self) -> dict[str, int]:
        return {
            "diagnostic": self.llm_monthly_quota_diagnostic,
            "cv": self.llm_monthly_quota_cv,
            "lettre": self.llm_monthly_quota_lettre,
            "compatibility": self.llm_monthly_quota_compatibility,
            "interview_prep": self.llm_monthly_quota_interview_prep,
            "ats_prefill": self.llm_monthly_quota_ats_prefill,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
