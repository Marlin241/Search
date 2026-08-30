import sentry_sdk

from app.config import get_settings

# Request paths whose bodies carry CV / offer / letter text - never sent to
# the error tracker.
_SENSITIVE_PREFIXES = (
    "/diagnostics",
    "/personalization",
    "/candidate-profile/cv",
    "/job-search/compatibility-detail",
    "/interview-prep",
    "/saved-jobs",
)
_SENSITIVE_VAR_HINTS = (
    "cv",
    "resume",
    "cv_text",
    "offer_text",
    "letter",
    "dossier",
    "password",
    "token",
)


def _request_path(url: str) -> str:
    after_scheme = url.split("://", 1)[-1]
    slash = after_scheme.find("/")
    return after_scheme[slash:] if slash != -1 else "/"


def _scrub_frames(event: dict) -> None:
    for value in event.get("exception", {}).get("values", []):
        for frame in value.get("stacktrace", {}).get("frames", []):
            varz = frame.get("vars")
            if not isinstance(varz, dict):
                continue
            for name in list(varz):
                if any(hint in name.lower() for hint in _SENSITIVE_VAR_HINTS):
                    varz[name] = "[scrubbed]"


def _before_send(event: dict, hint: dict) -> dict | None:
    request = event.get("request")
    if isinstance(request, dict):
        path = _request_path(request.get("url", ""))
        if any(path.startswith(p) for p in _SENSITIVE_PREFIXES):
            event["request"] = {
                k: request[k] for k in ("url", "method") if k in request
            }
        else:
            request.pop("data", None)
            request.pop("cookies", None)
    _scrub_frames(event)
    return event


def init_sentry() -> None:
    settings = get_settings()
    if not settings.glitchtip_dsn:
        return
    sentry_sdk.init(
        dsn=settings.glitchtip_dsn,
        environment=settings.environment,
        send_default_pii=False,
        traces_sample_rate=0.0,
        before_send=_before_send,  # type: ignore[arg-type]  # plain-dict signature, tested directly
    )
