import logging
import re
from time import perf_counter
from uuid import uuid4

from app.core.errors import AppError, error_response

logger = logging.getLogger(__name__)


def configure_logging(level):
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def add_http_middlewares(app, settings):
    @app.middleware("http")
    async def request_logging(request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        started = perf_counter()
        content_length = request.headers.get("Content-Length")
        is_upload = request.method == "POST" and re.fullmatch(
            r"/api/v1/tasks/[^/]+/media", request.url.path
        )
        limit = (
            settings.max_upload_mb * 1024 * 1024 + 1024 * 1024
            if is_upload
            else settings.max_request_body_kb * 1024
        )
        if content_length and content_length.isdecimal() and int(content_length) > limit:
            response = error_response(
                AppError(
                    "MEDIA_TOO_LARGE",
                    "Upload exceeds the configured limit.",
                    413,
                    {"max_upload_mb": settings.max_upload_mb},
                )
                if is_upload
                else AppError(
                    "PAYLOAD_TOO_LARGE", "Request body exceeds the configured limit.", 413
                )
            )
        else:
            response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            (perf_counter() - started) * 1000,
        )
        return response
