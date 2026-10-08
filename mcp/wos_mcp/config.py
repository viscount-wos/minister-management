"""Configuration from environment variables.

Secrets (MCP_BEARER_TOKEN, MCP_PUBLIC_BEARER_TOKEN, WOS_ADMIN_PASSWORD) are held
here and never logged; ``Config.__repr__`` redacts them.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

MIN_TOKEN_LENGTH = 32


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, '').strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise SystemExit(f'{name} must be an integer')


@dataclass(frozen=True)
class Config:
    api_base: str
    host: str = '127.0.0.1'
    port: int = 8094
    # Secrets: repr=False keeps them out of any accidental log of the config.
    admin_bearer_token: str | None = field(default=None, repr=False)
    public_bearer_token: str | None = field(default=None, repr=False)
    admin_password: str | None = field(default=None, repr=False)
    rate_limit_per_minute: int = 120
    api_timeout_seconds: float = 15.0
    allowed_hosts: tuple[str, ...] = ()
    trust_proxy: bool = False

    @property
    def admin_enabled(self) -> bool:
        return bool(self.admin_bearer_token) and len(self.admin_bearer_token) >= MIN_TOKEN_LENGTH

    @classmethod
    def from_env(cls) -> 'Config':
        api_base = os.getenv('WOS_API_BASE', '').strip().rstrip('/')
        if not api_base:
            raise SystemExit('WOS_API_BASE is required (e.g. http://127.0.0.1:8094)')
        if not api_base.startswith(('http://', 'https://')):
            raise SystemExit('WOS_API_BASE must start with http:// or https://')
        admin_token = os.getenv('MCP_BEARER_TOKEN') or None
        if admin_token and len(admin_token) < MIN_TOKEN_LENGTH:
            logger.warning('MCP_BEARER_TOKEN is shorter than %d characters: admin endpoint DISABLED',
                           MIN_TOKEN_LENGTH)
        elif not admin_token:
            logger.warning('MCP_BEARER_TOKEN not set: admin endpoint DISABLED')
        hosts = tuple(h.strip() for h in os.getenv('MCP_ALLOWED_HOSTS', '').split(',') if h.strip())
        return cls(
            api_base=api_base,
            host=os.getenv('MCP_HOST', '127.0.0.1'),
            port=_int_env('MCP_PORT', _int_env('PORT', 8094)),  # Cloud Run sets PORT
            admin_bearer_token=admin_token,
            public_bearer_token=os.getenv('MCP_PUBLIC_BEARER_TOKEN') or None,
            admin_password=os.getenv('WOS_ADMIN_PASSWORD') or None,
            rate_limit_per_minute=_int_env('MCP_RATE_LIMIT_PER_MINUTE', 120),
            api_timeout_seconds=float(_int_env('WOS_API_TIMEOUT_SECONDS', 15)),
            allowed_hosts=hosts,
            trust_proxy=os.getenv('MCP_TRUST_PROXY', '').lower() in ('1', 'true', 'yes'),
        )
