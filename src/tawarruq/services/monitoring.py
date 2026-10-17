"""In-process HTTP request metrics for ops monitoring."""

from __future__ import annotations

import threading
import time
from collections import defaultdict


class _MetricsStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.requests_total = 0
        self.errors_total = 0
        self.latency_ms_sum = 0.0
        self.by_status: dict[int, int] = defaultdict(int)
        self.by_path: dict[str, int] = defaultdict(int)

    def record(self, path: str, status_code: int, latency_ms: float) -> None:
        with self._lock:
            self.requests_total += 1
            self.latency_ms_sum += latency_ms
            self.by_status[status_code] += 1
            self.by_path[path] += 1
            if status_code >= 400:
                self.errors_total += 1

    def snapshot(self) -> dict:
        with self._lock:
            avg = self.latency_ms_sum / self.requests_total if self.requests_total else 0.0
            return {
                "requests_total": self.requests_total,
                "errors_total": self.errors_total,
                "latency_ms_avg": round(avg, 2),
                "by_status": dict(self.by_status),
                "top_paths": dict(sorted(self.by_path.items(), key=lambda item: item[1], reverse=True)[:10]),
            }


_store = _MetricsStore()


def record_request(path: str, status_code: int, latency_ms: float) -> None:
    _store.record(path, status_code, latency_ms)


def get_http_metrics() -> dict:
    return _store.snapshot()


class RequestMetricsMiddleware:
    """Starlette-compatible ASGI middleware wrapper."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        path = scope.get("path", "")
        status_holder = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)
        latency_ms = (time.perf_counter() - start) * 1000
        record_request(path, status_holder["code"], latency_ms)
