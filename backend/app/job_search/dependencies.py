from functools import lru_cache

from app.config import get_settings
from app.job_search.adzuna import AdzunaClient
from app.job_search.france_travail import FranceTravailClient
from app.job_search.greenhouse import GreenhouseJobBoardClient
from app.job_search.lever import LeverJobBoardClient


@lru_cache
def get_job_search_clients() -> dict[str, object]:
    settings = get_settings()
    return {
        "france_travail": FranceTravailClient(
            client_id=settings.france_travail_client_id,
            client_secret=settings.france_travail_client_secret,
        ),
        "adzuna": AdzunaClient(
            app_id=settings.adzuna_app_id,
            app_key=settings.adzuna_app_key,
            country=settings.adzuna_country,
        ),
        "greenhouse": GreenhouseJobBoardClient(),
        "lever": LeverJobBoardClient(),
    }
