import ipaddress
import socket
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

ALLOWED_SCHEMES = {"http", "https"}
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 5
USER_AGENT = "Mozilla/5.0 (compatible; ATSDiagnosticBot/1.0)"

# RFC 6598 Carrier-Grade NAT / Shared Address Space. Not covered by
# ipaddress.IPv4Address's is_private/is_reserved/etc. properties, but used
# by real cloud NAT/internal-LB setups and by Tailscale's overlay network -
# a real SSRF target class, so it needs an explicit block.
_SHARED_ADDRESS_SPACE = ipaddress.ip_network("100.64.0.0/10")


class ScrapingError(Exception):
    pass


def _validate_url(url: str) -> None:
    """Reject non-http(s) schemes and hostnames that resolve to
    private/internal/reserved addresses. Fails closed: resolution
    failures and unparseable URLs are rejected, not allowed through."""
    parts = urlsplit(url)
    if parts.scheme not in ALLOWED_SCHEMES:
        raise ScrapingError(
            f"URL scheme '{parts.scheme}' is not allowed; only http/https are permitted"
        )

    hostname = parts.hostname
    if not hostname:
        raise ScrapingError("URL is missing a hostname")

    try:
        addrinfo = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ScrapingError(f"Could not resolve hostname '{hostname}': {exc}") from exc
    if not addrinfo:
        raise ScrapingError(f"Could not resolve hostname '{hostname}'")

    for info in addrinfo:
        sockaddr = info[4]
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
            or (ip.version == 4 and ip in _SHARED_ADDRESS_SPACE)
        ):
            raise ScrapingError(
                f"URL host '{hostname}' resolves to a disallowed address: {sockaddr[0]}"
            )


def _read_body_with_cap(response: httpx.Response) -> bytes:
    """Read a streamed response body, aborting before it grows past
    MAX_RESPONSE_BYTES so a hostile or misbehaving server can't exhaust
    memory. Checks Content-Length up front as a fast path, but the real
    guarantee comes from capping bytes actually read off the wire."""
    content_length = response.headers.get("content-length")
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except ValueError:
            declared_length = None
        if declared_length is not None and declared_length > MAX_RESPONSE_BYTES:
            raise ScrapingError(
                f"Response too large: Content-Length {declared_length} exceeds "
                f"{MAX_RESPONSE_BYTES} byte limit"
            )

    body = bytearray()
    for chunk in response.iter_bytes():
        body.extend(chunk)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ScrapingError(
                f"Response exceeded {MAX_RESPONSE_BYTES} byte limit while streaming"
            )
    return bytes(body)


def scrape_offer(url: str) -> str:
    current_url = url
    body: bytes | None = None

    try:
        with httpx.Client(timeout=10.0, follow_redirects=False) as client:
            for _ in range(MAX_REDIRECTS + 1):
                _validate_url(current_url)
                with client.stream(
                    "GET", current_url, headers={"User-Agent": USER_AGENT}
                ) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise ScrapingError(
                                "Redirect response missing Location header"
                            )
                        current_url = str(httpx.URL(current_url).join(location))
                        continue

                    response.raise_for_status()
                    body = _read_body_with_cap(response)
                break
            else:
                raise ScrapingError(f"Too many redirects (exceeded {MAX_REDIRECTS})")
    except httpx.HTTPError as exc:
        raise ScrapingError(f"Failed to fetch offer URL: {exc}") from exc

    if body is None:
        # Unreachable in practice: the loop above only exits via `break`
        # after assigning body, or via an exception. Guarded explicitly
        # (rather than via `assert`) so this invariant holds even when
        # Python is run with optimizations (`-O`) that strip asserts.
        raise ScrapingError("Failed to fetch offer URL: no response body")

    soup = BeautifulSoup(body, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)

    if len(text) < 200:
        raise ScrapingError(
            "Scraped content too short, likely blocked or JS-rendered page"
        )
    return text
