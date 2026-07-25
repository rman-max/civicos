from __future__ import annotations

import json
import logging
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from threading import Lock
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from civicos_api.auth import AuthenticationError, Authenticator, principal_headers, problem_response

if TYPE_CHECKING:
    from civicos_api.config import Settings

logger = logging.getLogger("civicos.api")


class JsonFormatter(logging.Formatter):
    """Emit one redaction-safe JSON object per application log event."""

    def format(self, record: logging.LogRecord) -> str:
        event: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        civic_fields = getattr(record, "civicos", None)
        if isinstance(civic_fields, dict):
            event.update(civic_fields)
        if record.exc_info:
            event["exception"] = self.formatException(record.exc_info)
        return json.dumps(event, separators=(",", ":"), default=str)


def configure_logging(log_level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    application_logger = logging.getLogger("civicos")
    application_logger.handlers = [handler]
    application_logger.setLevel(log_level.upper())
    application_logger.propagate = False


@dataclass
class Metrics:
    request_counts: dict[tuple[str, str, int], int] = field(
        default_factory=lambda: defaultdict(int)
    )
    request_durations: dict[tuple[str, str], list[float]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _lock: Lock = field(default_factory=Lock)

    def observe(self, method: str, path: str, status_code: int, duration_seconds: float) -> None:
        with self._lock:
            self.request_counts[(method, path, status_code)] += 1
            durations = self.request_durations[(method, path)]
            durations.append(duration_seconds)
            if len(durations) > 1_000:
                del durations[: len(durations) - 1_000]

    def render_prometheus(self) -> str:
        lines = [
            "# HELP civicos_http_requests_total HTTP responses by route and status.",
            "# TYPE civicos_http_requests_total counter",
        ]
        with self._lock:
            for (method, path, status_code), count in sorted(self.request_counts.items()):
                labels = f'method="{method}",path="{path}",status="{status_code}"'
                lines.append(f"civicos_http_requests_total{{{labels}}} {count}")
            lines.extend(
                [
                    "# HELP civicos_http_request_duration_seconds Recent request latency sum and "
                    "count.",
                    "# TYPE civicos_http_request_duration_seconds summary",
                ]
            )
            for (method, path), durations in sorted(self.request_durations.items()):
                labels = f'method="{method}",path="{path}"'
                lines.append(
                    f"civicos_http_request_duration_seconds_sum{{{labels}}} {sum(durations)}"
                )
                lines.append(
                    f"civicos_http_request_duration_seconds_count{{{labels}}} {len(durations)}"
                )
        return "\n".join(lines) + "\n"


class InMemoryRateLimiter:
    """Process-local burst protection; production needs a proxy-enforced global limit too."""

    def __init__(self, requests_per_minute: int) -> None:
        self._requests_per_minute = requests_per_minute
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - 60
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self._requests_per_minute:
                return False
            events.append(now)
            return True


class AuthenticationMiddleware:
    """Authenticates every versioned API route and replaces legacy client scope headers."""

    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        settings: Settings,
        authenticator: Authenticator,
    ) -> None:
        self.app = app
        self._settings = settings
        self._authenticator = authenticator

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[..., Awaitable[Any]],
        send: Callable[..., Awaitable[None]],
    ) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") == "OPTIONS"
            or not str(scope.get("path", "")).startswith("/v1/")
        ):
            await self.app(scope, receive, send)
            return
        if self._settings.auth_mode == "development":
            await self.app(scope, receive, send)
            return
        authorization = _header_value(scope.get("headers", []), b"authorization")
        try:
            principal = await self._authenticator.authenticate(authorization)
        except AuthenticationError as error:
            await _send_json(send, 401, problem_response(401, str(error)))
            return
        scope["headers"] = principal_headers(principal, list(scope.get("headers", [])))
        scope.setdefault("state", {})["principal"] = principal
        await self.app(scope, receive, send)


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, app: Any, metrics: Metrics, limiter: InMemoryRateLimiter, settings: Settings
    ) -> None:
        super().__init__(app)
        self._metrics = metrics
        self._limiter = limiter
        self._settings = settings

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        if request.url.path.startswith(("/v1/", "/public/", "/auth/")) and not self._limiter.allow(
            _client_key(request)
        ):
            limited_response = JSONResponse(
                status_code=429,
                content={
                    "type": "https://civicos.org/problems/rate-limit",
                    "title": "Too many requests",
                    "status": 429,
                    "detail": "Try again shortly.",
                },
            )
            return self._finalize(request, limited_response, 0.0)
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                body_is_too_large = int(content_length) > self._settings.request_max_bytes
            except ValueError:
                body_is_too_large = True
            if body_is_too_large:
                oversized_response = JSONResponse(
                    status_code=413,
                    content={
                        "type": "https://civicos.org/problems/request-too-large",
                        "title": "Request body too large",
                        "status": 413,
                        "detail": "The request exceeds the configured API body limit.",
                    },
                )
                return self._finalize(request, oversized_response, 0.0)
        started_at = time.perf_counter()
        response: Response
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled_request_error", extra={"civicos": _request_fields(request)})
            response = JSONResponse(
                status_code=500,
                content={
                    "type": "https://civicos.org/problems/internal-error",
                    "title": "Internal server error",
                    "status": 500,
                    "detail": (
                        "The request could not be completed. Refer to the request ID when "
                        "contacting support."
                    ),
                },
            )
        return self._finalize(request, response, time.perf_counter() - started_at)

    def _finalize(self, request: Request, response: Response, duration_seconds: float) -> Response:
        route_path = _route_path(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["Cache-Control"] = "no-store"
        if self._settings.environment == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        self._metrics.observe(request.method, route_path, response.status_code, duration_seconds)
        logger.info(
            "request_completed",
            extra={
                "civicos": {
                    **_request_fields(request),
                    "status_code": response.status_code,
                    "duration_ms": round(duration_seconds * 1_000, 2),
                }
            },
        )
        return response


def _header_value(headers: list[tuple[bytes, bytes]], name: bytes) -> str | None:
    for header_name, value in headers:
        if header_name.lower() == name:
            return value.decode("latin-1")
    return None


async def _send_json(
    send: Callable[..., Awaitable[None]], status_code: int, content: dict[str, Any]
) -> None:
    body = json.dumps(content, separators=(",", ":")).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [(b"content-type", b"application/problem+json")],
        }
    )
    await send({"type": "http.response.body", "body": body})


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _route_path(request: Request) -> str:
    route = request.scope.get("route")
    return str(getattr(route, "path", None) or request.url.path)


def _request_fields(request: Request) -> dict[str, Any]:
    return {
        "request_id": getattr(request.state, "request_id", None),
        "method": request.method,
        "path": _route_path(request),
    }
