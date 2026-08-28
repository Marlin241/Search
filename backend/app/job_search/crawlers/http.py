import ipaddress
import socket
from urllib.parse import urlsplit

import httpx

_ALLOWED_SCHEMES = {"http", "https"}
_MAX_REDIRECTS = 5


class CrawlFetchError(Exception):
    """Raised when a crawler cannot retrieve a URL: bad scheme, a host
    outside the allowed set, a hostname resolving to a private/internal
    address (SSRF guard), a transport error, a >= 400 status, too many
    redirects, or a body over the cap."""


def _disallowed_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # Unwrap IPv4-mapped / IPv4-compatible IPv6 (e.g. ::ffff:127.0.0.1) and
    # 6to4 / Teredo tunnels: their `is_private` / `is_loopback` on the IPv6
    # object do not reflect the embedded IPv4 address, so `::ffff:169.254.0.1`
    # would otherwise slip past every check below.
    if isinstance(ip, ipaddress.IPv6Address):
        embedded = ip.ipv4_mapped or ip.sixtofour or ip.teredo
        if isinstance(embedded, tuple):  # teredo -> (server, client)
            return any(_disallowed_ip(part) for part in embedded)
        if embedded is not None:
            return _disallowed_ip(embedded)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _validate_url(url: str, allowed_hosts: frozenset[str] | None) -> None:
    parts = urlsplit(url)
    if parts.scheme not in _ALLOWED_SCHEMES:
        raise CrawlFetchError(f"scheme '{parts.scheme}' not allowed")
    hostname = parts.hostname
    if not hostname:
        raise CrawlFetchError("missing hostname")
    if allowed_hosts is not None and hostname.lower() not in allowed_hosts:
        raise CrawlFetchError(f"host '{hostname}' is not in the allowed set")
    try:
        addrinfo = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise CrawlFetchError(f"cannot resolve '{hostname}': {exc}") from exc
    for info in addrinfo:
        ip = ipaddress.ip_address(info[4][0])
        if _disallowed_ip(ip):
            raise CrawlFetchError(f"host '{hostname}' resolves to disallowed {ip}")


def fetch_text(
    url: str,
    http_client: httpx.Client,
    *,
    max_bytes: int = 3_000_000,
    allowed_hosts: frozenset[str] | None = None,
) -> str:
    """GET ``url`` and return its body as text. Validates the scheme, the
    host (against ``allowed_hosts`` when given) and every resolved address
    on each redirect hop, follows up to 5 redirects, and aborts a response
    body that grows past ``max_bytes``. The client should be built with
    ``follow_redirects=False`` so each hop is revalidated here.

    Resolution is checked separately from httpx's own connection lookup, so
    a determined DNS-rebinding attacker who controls an allowed host's DNS
    could still race the two; pinning the crawl to a fixed ``allowed_hosts``
    set is the primary defence against redirect-based SSRF."""
    current = url
    try:
        for _ in range(_MAX_REDIRECTS + 1):
            _validate_url(current, allowed_hosts)
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
