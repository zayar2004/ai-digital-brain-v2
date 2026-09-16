"""
Tiny in-memory rate limiter.

Suitable for single-process Termux deployment.
For multi-process / production, swap with Redis or a DB-backed limiter.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from functools import wraps

from flask import jsonify, request

_lock = threading.Lock()
_buckets: dict[str, deque[float]] = defaultdict(deque)


def _key(scope: str) -> str:
    ip = request.remote_addr or "unknown"
    return f"{scope}:{ip}"


def allow(scope: str, max_calls: int, window_seconds: int) -> bool:
    """Return True if the current request is allowed."""
    now = time.monotonic()
    cutoff = now - window_seconds
    k = _key(scope)
    with _lock:
        q = _buckets[k]
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= max_calls:
            return False
        q.append(now)
        return True


def rate_limit(scope: str, max_calls: int, window_seconds: int):
    """
    Decorator: rate limit a view by client IP.

    Usage:
        @rate_limit("login", max_calls=10, window_seconds=60)
        def login(): ...
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not allow(scope, max_calls, window_seconds):
                if request.path.startswith("/api/"):
                    return jsonify(
                        {
                            "success": False,
                            "error": {
                                "code": "rate_limited",
                                "message": "Too many requests. Try again later.",
                            },
                        }
                    ), 429
                return (
                    "Too many requests. Please wait and try again.",
                    429,
                )
            return fn(*args, **kwargs)

        return wrapper

    return decorator
