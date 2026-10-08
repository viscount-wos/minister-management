"""Consistent JSON errors for the whole API.

Every error response has the shape::

    {"error": "<human message>", "code": "<MACHINE_CODE>", "field": "<field or null>"}

Raise ``ApiError`` (or one of the helpers) anywhere inside a request; the
handler registered by ``register_error_handlers`` turns it into JSON.
"""
import logging
import sqlite3

from flask import jsonify, request
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, status, code, message, field=None, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.field = field
        self.details = details

    def to_response(self):
        body = {'error': self.message, 'code': self.code, 'field': self.field}
        if self.details is not None:
            body['details'] = self.details
        return jsonify(body), self.status


def validation_error(message, field=None, details=None):
    return ApiError(400, 'VALIDATION_ERROR', message, field=field, details=details)


def not_found(message='Not found', code='NOT_FOUND'):
    return ApiError(404, code, message)


def conflict(message, code='CONFLICT'):
    return ApiError(409, code, message)


def get_json_body(required=True):
    """Parse the request body as a JSON object or raise INVALID_JSON."""
    data = request.get_json(silent=True)
    if data is None:
        if not required and not request.data:
            return {}
        raise ApiError(400, 'INVALID_JSON', 'Request body must be a JSON object')
    if not isinstance(data, dict):
        raise ApiError(400, 'INVALID_JSON', 'Request body must be a JSON object')
    return data


_HTTP_CODES = {
    400: 'BAD_REQUEST',
    401: 'UNAUTHORIZED',
    403: 'FORBIDDEN',
    404: 'NOT_FOUND',
    405: 'METHOD_NOT_ALLOWED',
    413: 'PAYLOAD_TOO_LARGE',
}


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def _api_error(err):
        return err.to_response()

    @app.errorhandler(HTTPException)
    def _http_error(err):
        code = _HTTP_CODES.get(err.code, 'HTTP_ERROR')
        return jsonify({'error': err.description or err.name, 'code': code, 'field': None}), err.code

    @app.errorhandler(sqlite3.IntegrityError)
    def _integrity(err):
        # e.g. two simultaneous first submissions for one FID; the client can simply retry
        logger.warning('Integrity error on %s %s: %s', request.method, request.path, err)
        return jsonify({'error': 'Conflicting concurrent change, please retry', 'code': 'CONFLICT',
                        'field': None}), 409

    @app.errorhandler(Exception)
    def _unhandled(err):
        logger.error('Unhandled error on %s %s', request.method, request.path, exc_info=err)
        return jsonify({'error': 'Internal server error', 'code': 'INTERNAL_ERROR', 'field': None}), 500
