import httpx
from bs4 import BeautifulSoup


class ScrapingError(Exception):
    pass


def scrape_offer(url: str) -> str:
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.get(
                url, headers={"User-Agent": "Mozilla/5.0 (compatible; ATSDiagnosticBot/1.0)"}
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ScrapingError(f"Failed to fetch offer URL: {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)

    if len(text) < 200:
        raise ScrapingError("Scraped content too short, likely blocked or JS-rendered page")
    return text
