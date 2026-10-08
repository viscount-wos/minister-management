"""Admin authentication: the ONE place that knows how admins log in.

v1.4 handed out the fixed strings 'admin-token'/'minister-token' and accepted
them as auth, so any client could call admin endpoints. Tokens are now signed
with SECRET_KEY (itsdangerous URLSafeTimedSerializer), carry {role} and expire
after 12 hours. Replace this module to move to real accounts later.

Known limits (accepted, see docs/SPEC.md): tokens cannot be revoked one by one.
Rotating ADMIN_PASSWORD does NOT invalidate tokens already issued (they live up
to 12 h); rotating SECRET_KEY invalidates all of them. A bare token (no
"Bearer ") is accepted for v1.4 frontend compatibility.

Login throttling (M3): an in-process limiter (adequate because production runs
exactly one instance) counts FAILED logins per client IP and globally. After
``LOGIN_FREE_FAILURES`` failures an IP is locked out with exponential backoff
(1 s, 2 s, 4 s ... capped at 15 min); while locked, every attempt is answered
429 TOO_MANY_ATTEMPTS without checking the password. A global failure budget
per minute protects against distributed guessing. Success resets that IP.
"""
import functools
import hashlib
import hmac
import logging
import threading
import time

from flask import Blueprint, current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from core.errors import ApiError, get_json_body

logger = logging.getLogger(__name__)

TOKEN_MAX_AGE = 12 * 60 * 60
TOKEN_SALT = 'wos-events-admin-token'
ROLES = ('admin', 'minister')

bp = Blueprint('auth', __name__)

LOGIN_FREE_FAILURES = 5          # per IP before the backoff starts
LOGIN_BACKOFF_BASE = 1.0         # seconds; doubles per extra failure
LOGIN_BACKOFF_MAX = 15 * 60
LOGIN_IP_FORGET_AFTER = 60 * 60  # an IP's failure count decays after an hour of quiet
LOGIN_GLOBAL_WINDOW = 60
LOGIN_GLOBAL_MAX_FAILURES = 30   # failures per window across all IPs before everyone waits


class LoginLimiter:
    """Failed-login throttle. Thread-safe; state lives in this process only."""

    def __init__(self, free=LOGIN_FREE_FAILURES, base=LOGIN_BACKOFF_BASE, cap=LOGIN_BACKOFF_MAX,
                 global_window=LOGIN_GLOBAL_WINDOW, global_max=LOGIN_GLOBAL_MAX_FAILURES,
                 forget_after=LOGIN_IP_FORGET_AFTER, clock=time.monotonic):
        self.free, self.base, self.cap = free, base, cap
        self.global_window, self.global_max, self.forget_after = global_window, global_max, forget_after
        self.clock = clock
        self._lock = threading.Lock()
        self._ips = {}       # ip -> [failures, locked_until, last_failure]
        self._global = []    # timestamps of recent failures

    def _prune(self, now):
        cutoff = now - self.global_window
        self._global = [t for t in self._global if t > cutoff]
        if len(self._ips) > 10000:  # bound memory under a spray of source addresses
            for ip in [ip for ip, st in self._ips.items() if now - st[2] > self.forget_after]:
                del self._ips[ip]

    def retry_after(self, ip):
        """Seconds the caller must wait before an attempt is evaluated (0 = go ahead)."""
        now = self.clock()
        with self._lock:
            self._prune(now)
            wait = 0.0
            st = self._ips.get(ip)
            if st:
                if now - st[2] > self.forget_after:
                    del self._ips[ip]
                else:
                    wait = max(wait, st[1] - now)
            if len(self._global) >= self.global_max:
                wait = max(wait, self._global[0] + self.global_window - now)
            return max(0.0, wait)

    def failure(self, ip):
        now = self.clock()
        with self._lock:
            st = self._ips.setdefault(ip, [0, 0.0, now])
            if now - st[2] > self.forget_after:
                st[0] = 0
            st[0] += 1
            st[2] = now
            if st[0] >= self.free:
                st[1] = now + min(self.cap, self.base * (2 ** (st[0] - self.free)))
            self._global.append(now)

    def success(self, ip):
        with self._lock:
            self._ips.pop(ip, None)


def _limiter():
    lim = current_app.extensions.get('wos_login_limiter')
    if lim is None:
        lim = current_app.extensions.setdefault('wos_login_limiter', LoginLimiter())
    return lim


def client_ip():
    """Client address for throttling.

    Proxies APPEND to X-Forwarded-For, so only the right-most TRUSTED_PROXY_HOPS entries can be trusted.
    Cloud Run (run.app URL or domain mapping) adds exactly one: the real client address (default 1).
    Behind an extra external load balancer set TRUSTED_PROXY_HOPS=2; with no proxy at all, 0.
    """
    hops = int(current_app.config.get('TRUSTED_PROXY_HOPS', 1) or 0)
    parts = [x.strip() for x in request.headers.get('X-Forwarded-For', '').split(',') if x.strip()]
    if hops > 0 and parts:
        return parts[-min(hops, len(parts))]
    return request.remote_addr or '?'


def _serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt=TOKEN_SALT)


def issue_token(role):
    if role not in ROLES:
        raise ValueError(f'unknown role {role!r}')
    return _serializer().dumps({'role': role})


def verify_token(token):
    """Return the role for a valid token or raise ApiError(401)."""
    max_age = current_app.config.get('TOKEN_MAX_AGE', TOKEN_MAX_AGE)
    try:
        payload = _serializer().loads(token, max_age=max_age)
    except SignatureExpired:
        raise ApiError(401, 'TOKEN_EXPIRED', 'Session expired, please log in again')
    except BadSignature:
        raise ApiError(401, 'INVALID_TOKEN', 'Invalid token')
    role = payload.get('role') if isinstance(payload, dict) else None
    if role not in ROLES:
        raise ApiError(401, 'INVALID_TOKEN', 'Invalid token')
    return role


def _token_from_request():
    header = request.headers.get('Authorization', '').strip()
    if not header:
        raise ApiError(401, 'UNAUTHORIZED', 'Authorization required')
    # v1.4 frontend sometimes sent the bare token; accept both forms.
    if header.lower().startswith('bearer '):
        header = header[7:].strip()
    if not header:
        raise ApiError(401, 'UNAUTHORIZED', 'Authorization required')
    return header


def require_admin(fn):
    """Decorator: 401 unless the request carries a valid, unexpired admin/minister token."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        g.admin_role = verify_token(_token_from_request())
        return fn(*args, **kwargs)
    return wrapper


def _digest(value):
    return hashlib.sha256(value.encode('utf-8')).digest()


def _check_password(supplied):
    """Return the role for a matching password, else None.

    Constant time: both roles are always compared, on fixed-length SHA-256 digests,
    so neither the matching role nor the password length leaks through timing.
    """
    supplied_d = _digest(supplied)
    role_found = None
    for role, key in (('admin', 'ADMIN_PASSWORD'), ('minister', 'MINISTER_PASSWORD')):
        expected = current_app.config.get(key)
        enabled = bool(expected)  # role disabled when no password configured
        match = hmac.compare_digest(supplied_d, _digest(expected or '\x00disabled'))
        if enabled and match and role_found is None:
            role_found = role
    return role_found


@bp.route('/api/admin/login', methods=['POST'])
def login():
    ip = client_ip()
    limiter = _limiter()
    wait = limiter.retry_after(ip)
    if wait > 0:
        logger.warning('Throttled admin login attempt from %s (retry in %.0fs)', ip, wait)
        err = ApiError(429, 'TOO_MANY_ATTEMPTS', 'Too many failed login attempts, try again later',
                       details={'retry_after': int(wait + 0.999)})
        err.headers = {'Retry-After': str(int(wait + 0.999))}
        raise err
    data = get_json_body()
    password = data.get('password')
    if not isinstance(password, str) or not password:
        raise ApiError(400, 'VALIDATION_ERROR', 'Password is required', field='password')
    role = _check_password(password)
    if not role:
        limiter.failure(ip)
        logger.warning('Failed admin login attempt from %s', ip)
        raise ApiError(401, 'INVALID_PASSWORD', 'Invalid password')
    limiter.success(ip)
    logger.info('%s login successful from %s', role, ip)
    return jsonify({'token': issue_token(role), 'role': role,
                    'expires_in': current_app.config.get('TOKEN_MAX_AGE', TOKEN_MAX_AGE)})


@bp.route('/api/admin/me', methods=['GET'])
@require_admin
def me():
    return jsonify({'role': g.admin_role})
