from unittest.mock import patch

import pytest

from app.offer_ingestion.ingestion import get_offer_text, OfferIngestionError
from app.offer_ingestion.scraper import ScrapingError


def test_returns_pasted_text_when_provided():
    assert get_offer_text("Some offer text", None) == "Some offer text"


def test_scrapes_url_when_no_text_provided():
    with patch("app.offer_ingestion.ingestion.scrape_offer", return_value="Scraped offer text") as mocked:
        result = get_offer_text(None, "https://example.com/job")
    mocked.assert_called_once_with("https://example.com/job")
    assert result == "Scraped offer text"


def test_scraping_failure_raises_ingestion_error():
    with patch("app.offer_ingestion.ingestion.scrape_offer", side_effect=ScrapingError("blocked")):
        with pytest.raises(OfferIngestionError):
            get_offer_text(None, "https://example.com/job")


def test_no_text_or_url_raises():
    with pytest.raises(OfferIngestionError):
        get_offer_text(None, None)
