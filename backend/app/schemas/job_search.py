from pydantic import BaseModel

from app.job_search.schemas import JobListing


class JobSearchResponse(BaseModel):
    listings: list[JobListing]
    unavailable_sources: list[str]
    search_id: str
    discovery_pending: bool


class JobSearchDiscoveryResponse(BaseModel):
    done: bool
    new_listings: list[JobListing]


class SavedSearchIn(BaseModel):
    keywords: str
    location: str | None = None
    contract_type: str | None = None
    remote: bool | None = None
    exclude_keywords: list[str] = []
    # Le frontend envoie le fuseau réel du navigateur (Intl.DateTimeFormat) ;
    # ce défaut ne joue que si le champ est omis (appel direct de l'API) -
    # Africa/Dakar (UTC, pas d'heure d'été) est plus proche du marché ciblé
    # que l'ancien défaut Europe/Paris.
    timezone: str = "Africa/Dakar"
    enabled: bool = True


class SavedSearchOut(BaseModel):
    keywords: str
    location: str | None
    contract_type: str | None
    remote: bool | None
    exclude_keywords: list[str]
    timezone: str
    enabled: bool
