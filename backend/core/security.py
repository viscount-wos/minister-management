"""Response hardening for every response (API, SPA shell and static assets).

- Security headers: CSP, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy and HSTS (HSTS only in
  production or when the request arrived over https, so the plain-http e2e/LAN stacks keep working).
- The CSP allows scripts from 'self' only, plus the SHA-256 hash of each inline <script> in the built
  index.html (the pre-paint language/RTL/theme script). The hashes are computed from the file actually being
  served, so a rebuilt index.html never needs a hand-edited hash.
- Caching: /assets/* (Vite's content-hashed file names) are immutable for a year; index.html, the SPA
  fallback and the API are no-cache.
- Compression: gzip / brotli for text responses (Flask-Compress). Compressed /assets/* bodies are cached in
  memory (they never change for a given name); API responses are never cached.
"""
import base64
import hashlib
import logging
import os
import re
import threading

from flask import request

logger = logging.getLogger(__name__)

ASSET_PREFIX = '/assets/'
IMMUTABLE = 'public, max-age=31536000, immutable'
NO_CACHE = 'no-cache'
NO_STORE = 'no-store'

_INLINE_SCRIPT_RE = re.compile(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', re.S | re.I)

PERMISSIONS_POLICY = 'camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()'


def inline_script_hashes(index_html_path):
    """CSP source expressions ('sha256-...') for every inline <script> in the given HTML file."""
    try:
        with open(index_html_path, encoding='utf-8') as fh:
            html = fh.read()
    except OSError:
        return []
    out = []
    for body in _INLINE_SCRIPT_RE.findall(html):
        digest = hashlib.sha256(body.encode('utf-8')).digest()
        out.append("'sha256-" + base64.b64encode(digest).decode('ascii') + "'")
    return out


def build_csp(script_hashes):
    script_src = ' '.join(["'self'", *script_hashes])
    return '; '.join([
        "default-src 'self'",
        f'script-src {script_src}',
        # Vite emits one stylesheet <link>; React style={{}} props go through the CSSOM, which CSP does not block.
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "manifest-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ])


class _AssetCompressionCache:
    """Flask-Compress cache backend that only ever stores compressed /assets/* bodies (immutable)."""

    def __init__(self, max_entries=256):
        self._data = {}
        self._lock = threading.Lock()
        self.max_entries = max_entries

    @staticmethod
    def _cacheable(key):
        return isinstance(key, str) and (';' + ASSET_PREFIX) in key

    def get(self, key):
        if not self._cacheable(key):
            return None
        with self._lock:
            return self._data.get(key)

    def set(self, key, value):
        if not self._cacheable(key):
            return
        with self._lock:
            if len(self._data) >= self.max_entries:
                self._data.clear()
            self._data[key] = value


def _cache_key(req):
    return req.path


def init_app(app):
    """Register compression and the header hook. Call after every blueprint is registered."""
    from flask_compress import Compress

    app.config.setdefault('COMPRESS_ALGORITHM', ['br', 'gzip'])
    app.config.setdefault('COMPRESS_BR_LEVEL', 5)
    app.config.setdefault('COMPRESS_LEVEL', 6)
    app.config.setdefault('COMPRESS_MIN_SIZE', 500)
    app.config.setdefault('COMPRESS_MIMETYPES', [
        'text/html', 'text/css', 'text/plain', 'text/xml', 'text/csv', 'text/javascript',
        'application/javascript', 'application/json', 'application/xml', 'image/svg+xml',
        'application/manifest+json',
    ])
    app.config.setdefault('COMPRESS_CACHE_BACKEND', _AssetCompressionCache)
    app.config.setdefault('COMPRESS_CACHE_KEY', _cache_key)
    Compress(app)

    index = os.path.join(app.config['STATIC_DIR'], 'index.html')
    csp_state = {'mtime': None, 'csp': build_csp([])}
    csp_lock = threading.Lock()

    def current_csp():
        # Recomputed only when index.html changes (a rebuild while running in dev); cheap stat otherwise.
        try:
            mtime = os.path.getmtime(index)
        except OSError:
            mtime = None
        if mtime != csp_state['mtime']:
            with csp_lock:
                csp_state['csp'] = build_csp(inline_script_hashes(index))
                csp_state['mtime'] = mtime
        return csp_state['csp']

    production = not app.config.get('DEV_MODE')

    # Registered after Compress: Flask runs after_request hooks in reverse order, so this one runs FIRST and
    # Compress still sees (and keeps) these headers.
    @app.after_request
    def _harden(response):
        h = response.headers
        h.setdefault('Content-Security-Policy', current_csp())
        h.setdefault('X-Content-Type-Options', 'nosniff')
        h.setdefault('X-Frame-Options', 'DENY')
        h.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        h.setdefault('Permissions-Policy', PERMISSIONS_POLICY)
        h.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        if production or request.is_secure or request.headers.get('X-Forwarded-Proto', '').lower() == 'https':
            h.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')

        path = request.path
        if path.startswith(ASSET_PREFIX) and response.status_code in (200, 304):
            h['Cache-Control'] = IMMUTABLE
        elif path.startswith('/api/') or path == '/health':
            h['Cache-Control'] = NO_STORE if path.startswith('/api/admin') else NO_CACHE
        elif 'Cache-Control' not in h or response.mimetype == 'text/html':
            h['Cache-Control'] = NO_CACHE
        return response
