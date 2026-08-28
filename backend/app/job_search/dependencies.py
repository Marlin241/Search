from functools import lru_cache

from app.config import get_settings
from app.job_search.adzuna import AdzunaClient
from app.job_search.france_travail import FranceTravailClient
from app.job_search.greenhouse import GreenhouseJobBoardClient
from app.job_search.jobicy import JobicyClient
from app.job_search.la_bonne_alternance import LaBonneAlternanceClient
from app.job_search.lever import LeverJobBoardClient
from app.job_search.reliefweb import ReliefWebClient
from app.job_search.rss_feeds import RssFeedClient


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
        "la_bonne_alternance": LaBonneAlternanceClient(
            api_key=settings.la_bonne_alternance_api_key
        ),
        "greenhouse": GreenhouseJobBoardClient(),
        "lever": LeverJobBoardClient(),
        "reliefweb": ReliefWebClient(
            appname=settings.reliefweb_appname,
            countries=settings.reliefweb_countries,
        ),
        "jobicy": JobicyClient(),
        "weworkremotely": RssFeedClient(
            "weworkremotely", settings.weworkremotely_feed_urls, remote_only=True
        ),
        "ngojobs": RssFeedClient(
            "ngojobs", settings.ngojobs_feed_urls, remote_only=False
        ),
    }
