"""Per-IP rate limits for the public player endpoints (FID lookups and submissions).

Players have no login: anyone can type any FID, so the lookups are the obvious thing to scrape and the
submissions the obvious thing to spam. An in-process sliding-window limiter is enough because production runs
exactly ONE instance (as for the admin login limiter in core/auth.py, which this shares ``client_ip`` with).

Buckets (requests per rolling minute per client IP; 0 disables the bucket):
- ``lookup``  RATE_LIMIT_LOOKUPS_PER_MIN, default 30: GET profile / current application / previous
  application / own assignments by FID.
- ``submit``  RATE_LIMIT_SUBMITS_PER_MIN, default 10: PUT application, PUT profile.

Over the limit -> 429 RATE_LIMITED with a Retry-After header (seconds) and ``details.retry_after``.
Requests carrying a valid admin token are not limited (the MCP server and admins act for many players).
"""
import functools
import math
import threading
import time
from collections import deque

from flask import current_app, request

from core.errors import ApiError

WINDOW_SECONDS = 60
DEFAULT_LIMITS = {'lookup': 30, 'submit': 10}
CONFIG_KEYS = {'lookup': 'RATE_LIMIT_LOOKUPS_PER_MIN', 'submit': 'RATE_LIMIT_SUBMITS_PER_MIN'}


class SlidingWindowLimiter:
    """At most ``limit`` hits per ``window`` seconds per key. Thread-safe; state lives in this process only."""

    def __init__(self, limit, window=WINDOW_SECONDS, clock=time.monotonic, max_keys=20000):
        self.limit, self.window, self.clock, self.max_keys = limit, window, clock, max_keys
        self._lock = threading.Lock()
        self._hits = {}  # key -> deque of timestamps

    def hit(self, key):
        """Record a request; return 0 if allowed, else the seconds until the next one is allowed."""
        if self.limit <= 0:
            return 0
        now = self.clock()
        cutoff = now - self.window
        with self._lock:
            q = self._hits.get(key)
            if q is None:
                if len(self._hits) >= self.max_keys:
                    self._prune(cutoff)
                q = self._hits[key] = deque()
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= self.limit:
                return max(0.001, q[0] + self.window - now)
            q.append(now)
            return 0

    def _prune(self, cutoff):
        for k in [k for k, q in self._hits.items() if not q or q[-1] <= cutoff]:
            del self._hits[k]


def _limit_for(bucket):
    raw = current_app.config.get(CONFIG_KEYS[bucket], DEFAULT_LIMITS[bucket])
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_LIMITS[bucket]


def _limiter(bucket):
    limiters = current_app.extensions.setdefault('wos_rate_limiters', {})
    limit = _limit_for(bucket)
    lim = limiters.get(bucket)
    if lim is None or lim.limit != limit:
        lim = limiters[bucket] = SlidingWindowLimiter(limit)
    return lim


def _is_admin_request():
    if not request.headers.get('Authorization'):
        return False
    from core.auth import _token_from_request, verify_token
    try:
        verify_token(_token_from_request())
        return True
    except ApiError:
        return False


def check(bucket):
    """Count this request against ``bucket``; raise 429 RATE_LIMITED when over the limit."""
    lim = _limiter(bucket)
    if lim.limit <= 0 or _is_admin_request():
        return
    from core.auth import client_ip
    wait = lim.hit(client_ip())
    if wait:
        secs = max(1, math.ceil(wait))
        err = ApiError(429, 'RATE_LIMITED', 'Too many requests, please wait a moment and try again',
                       details={'retry_after': secs})
        err.headers = {'Retry-After': str(secs)}
        raise err


def rate_limited(bucket):
    """Decorator for a public route: ``@rate_limited('lookup')`` or ``@rate_limited('submit')``."""
    if bucket not in DEFAULT_LIMITS:
        raise ValueError(f'unknown rate-limit bucket {bucket!r}')

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            check(bucket)
            return fn(*args, **kwargs)
        return wrapper
    return deco
