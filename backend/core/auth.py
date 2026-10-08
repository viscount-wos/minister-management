"""Admin authentication: the ONE place that knows how admins log in.

v1.4 handed out the fixed strings 'admin-token'/'minister-token' and accepted
them as auth, so any client could call admin endpoints. Tokens are now signed
with SECRET_KEY (itsdangerous URLSafeTimedSerializer), carry {role} and expire
after 12 hours. Replace this module to move to real accounts later.
"""
import functools
import hmac
import logging

from flask import Blueprint, current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from core.errors import ApiError, get_json_body

logger = logging.getLogger(__name__)

TOKEN_MAX_AGE = 12 * 60 * 60
TOKEN_SALT = 'wos-events-admin-token'
ROLES = ('admin', 'minister')

bp = Blueprint('auth', __name__)


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


def _check_password(supplied):
    """Return the role for a matching password, else None. Constant-time compare."""
    supplied_b = supplied.encode('utf-8')
    role_found = None
    for role, key in (('admin', 'ADMIN_PASSWORD'), ('minister', 'MINISTER_PASSWORD')):
        expected = current_app.config.get(key)
        if not expected:
            continue  # role disabled when no password configured
        if hmac.compare_digest(supplied_b, expected.encode('utf-8')) and role_found is None:
            role_found = role
    return role_found


@bp.route('/api/admin/login', methods=['POST'])
def login():
    data = get_json_body()
    password = data.get('password')
    if not isinstance(password, str) or not password:
        raise ApiError(400, 'VALIDATION_ERROR', 'Password is required', field='password')
    role = _check_password(password)
    if not role:
        logger.warning('Failed admin login attempt from %s', request.remote_addr)
        raise ApiError(401, 'INVALID_PASSWORD', 'Invalid password')
    logger.info('%s login successful', role)
    return jsonify({'token': issue_token(role), 'role': role,
                    'expires_in': current_app.config.get('TOKEN_MAX_AGE', TOKEN_MAX_AGE)})


@bp.route('/api/admin/me', methods=['GET'])
@require_admin
def me():
    return jsonify({'role': g.admin_role})
