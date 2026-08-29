from fastapi import Request


def client_ip(request: Request) -> str:
    """Client IP for rate-limiting keys.

    In prod the only trusted proxy is the host nginx, configured with
    `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for`, which
    APPENDS the real TCP peer as the LAST element. Any earlier elements are
    attacker-controlled, so we take the **last** hop, never the first -
    reading the first would let a client spoof `X-Forwarded-For` and get a
    fresh rate-limit bucket on every request.

    In dev (no proxy) there is no XFF and we fall back to the direct peer.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        hops = [h.strip() for h in xff.split(",") if h.strip()]
        if hops:
            return hops[-1]
    if request.client is not None:
        return request.client.host
    return "unknown"
