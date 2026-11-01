import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.services.session_activity_service import SESSION_HEADER, SessionActivityService

logger = logging.getLogger("WorkforceOS.requests")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed method=%s path=%s request_id=%s",
                request.method,
                request.url.path,
                request_id,
            )
            raise

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        if request.url.path not in ("/health", "/health/live", "/health/ready"):
            logger.info(
                "request method=%s path=%s status=%s duration_ms=%s request_id=%s",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
                request_id,
            )

        session_id = (request.headers.get(SESSION_HEADER) or "").strip()
        if (
            session_id
            and request.method.upper() != "OPTIONS"
            and request.url.path.startswith("/api/")
        ):
            try:
                SessionActivityService.log_api_call_from_request(
                    session_id=session_id,
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    duration_ms=elapsed_ms,
                    request_id=request_id,
                )
            except Exception:
                logger.exception("session_activity_middleware_failed")

        return response
