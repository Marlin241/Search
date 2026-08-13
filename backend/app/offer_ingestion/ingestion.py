from app.offer_ingestion.scraper import ScrapingError, scrape_offer


class OfferIngestionError(Exception):
    pass


def get_offer_text(text: str | None, url: str | None) -> str:
    if text and text.strip():
        return text.strip()
    if url:
        try:
            return scrape_offer(url)
        except ScrapingError as exc:
            raise OfferIngestionError(
                "Impossible de récupérer le contenu de cette offre automatiquement. "
                "Merci de coller le texte de l'offre manuellement."
            ) from exc
    raise OfferIngestionError("Merci de fournir le texte de l'offre ou son URL.")
