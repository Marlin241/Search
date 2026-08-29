from fastapi import Request


def client_ip(request: Request) -> str:
    """Best-effort client IP: first hop of X-Forwarded-For (set by the host
    nginx in prod), else the direct peer, else "unknown"."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"
