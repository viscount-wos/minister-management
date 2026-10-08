"""Turn API results into MCP tool results.

Success: ``structuredContent`` is the API's JSON body unchanged.
Failure: ``isError=true`` and ``structuredContent`` is the API's error body
(``{error, code, field}``) plus ``http_status``. Errors are returned, never
raised, so the caller always sees the machine-readable ``code``.
"""
from __future__ import annotations

import json
import re
from typing import Any

from mcp.types import CallToolResult, TextContent

from .api import ApiResult

# Characters allowed in a value that becomes one URL path segment. FIDs are digits
# on every write (the API enforces that); legacy imported FIDs may contain other
# word characters, so reads accept a slightly wider, still path-safe, set.
_SAFE_SEGMENT = re.compile(r'^[A-Za-z0-9_-]{1,64}$')


def _dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(',', ':'))


def ok(body: dict[str, Any]) -> CallToolResult:
    return CallToolResult(content=[TextContent(type='text', text=_dump(body))], structured_content=body)


def error(status: int, code: str, message: str, field: str | None = None,
          details: Any = None) -> CallToolResult:
    body: dict[str, Any] = {'error': message, 'code': code, 'field': field}
    if details is not None:
        body['details'] = details
    body['http_status'] = status
    return CallToolResult(content=[TextContent(type='text', text=_dump(body))],
                          structured_content=body, is_error=True)


def from_api(res: ApiResult) -> CallToolResult:
    if res.ok:
        return ok(res.body)
    body = dict(res.body)
    body.setdefault('error', 'API error')
    body.setdefault('code', 'HTTP_ERROR')
    body.setdefault('field', None)
    body['http_status'] = res.status
    return CallToolResult(content=[TextContent(type='text', text=_dump(body))],
                          structured_content=body, is_error=True)


def check_segment(name: str, value: Any) -> CallToolResult | None:
    """Reject values that could not be a valid id/key before they reach a URL."""
    if not isinstance(value, str) or not _SAFE_SEGMENT.match(value):
        return error(400, 'VALIDATION_ERROR',
                     f'{name} must be 1-64 letters, digits, "_" or "-"', field=name)
    return None
