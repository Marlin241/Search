import logging

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Register a single catch-all handler for otherwise-unhandled exceptions.

    `HTTPException` and `RequestValidationError` keep FastAPI's default
    handlers (their FR messages / 422 shape are already fine) - only truly
    unexpected errors are caught here, so no traceback ever reaches the
    client.
    """

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        event_id = sentry_sdk.capture_exception(exc)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Une erreur est survenue. L'équipe a été notifiée.",
                "error_id": event_id,
            },
        )
