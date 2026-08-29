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
    enabled_crawlers: list[str] = ["emploi_dakar"]
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
