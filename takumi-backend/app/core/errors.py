import logging

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def error_response(error: AppError):
    return JSONResponse(
        status_code=error.status_code,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "details": error.details,
            }
        },
    )


def feature_disabled(flag_env: str, checkpoint: int | None = None):
    return AppError(
        "FEATURE_DISABLED",
        f"{flag_env} is disabled in this deployment.",
        501,
        {"flag": flag_env, "checkpoint": checkpoint},
    )


def register_error_handlers(app):
    @app.exception_handler(AppError)
    async def app_error_handler(request, exc):
        return error_response(exc)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request, exc):
        errors = [{key: item[key] for key in ("loc", "msg", "type")} for item in exc.errors()]
        return error_response(
            AppError("VALIDATION_ERROR", "Request validation failed.", 422, {"errors": errors})
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request, exc):
        codes = {
            401: "UNAUTHENTICATED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            413: "PAYLOAD_TOO_LARGE",
        }
        return error_response(
            AppError(codes.get(exc.status_code, "HTTP_ERROR"), str(exc.detail), exc.status_code)
        )

    @app.exception_handler(Exception)
    async def internal_error_handler(request, exc):
        logger.error("Unhandled request exception", exc_info=exc)
        return error_response(AppError("INTERNAL_ERROR", "Internal server error.", 500))
