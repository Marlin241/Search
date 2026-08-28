import ipaddress
import socket
from urllib.parse import urlsplit

import httpx

_ALLOWED_SCHEMES = {"http", "https"}
_MAX_REDIRECTS = 5


class CrawlFetchError(Exception):
    """Raised when a crawler cannot retrieve a URL: bad scheme, a hostname
    resolving to a private/internal address (SSRF guard), a transport
    error, a >= 400 status, too many redirects, or a body over the cap."""


def _validate_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in _ALLOWED_SCHEMES:
        raise CrawlFetchError(f"scheme '{parts.scheme}' not allowed")
    hostname = parts.hostname
    if not hostname:
        raise CrawlFetchError("missing hostname")
    try:
        addrinfo = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise CrawlFetchError(f"cannot resolve '{hostname}': {exc}") from exc
    for info in addrinfo:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise CrawlFetchError(f"host '{hostname}' resolves to disallowed {ip}")


def fetch_text(
    url: str, http_client: httpx.Client, *, max_bytes: int = 3_000_000
) -> str:
    """GET ``url`` and return its body as text. Validates the scheme and
    the resolved host on every redirect hop, follows up to 5 redirects, and
    aborts a response body that grows past ``max_bytes``. The client should
    be built with ``follow_redirects=False`` so each hop is revalidated
    here."""
    current = url
    try:
        for _ in range(_MAX_REDIRECTS + 1):
            _validate_url(current)
            with http_client.stream("GET", current) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise CrawlFetchError("redirect without Location header")
                    current = str(httpx.URL(current).join(location))
                    continue
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise CrawlFetchError(f"response exceeded {max_bytes} bytes")
                return body.decode("utf-8", errors="replace")
        raise CrawlFetchError("too many redirects")
    except httpx.HTTPError as exc:
        raise CrawlFetchError(f"fetch failed for {url}: {exc}") from exc
