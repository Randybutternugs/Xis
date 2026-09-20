"""Request-parsing helpers shared by the JSON API blueprints."""

from flask import jsonify, request
from werkzeug.exceptions import BadRequest, NotFound


def int_arg(name, default, lo=None, hi=None, source=None):
    """Integer query/body parameter with bounds. Non-numeric -> 400, never 500.

    `source` defaults to request.args; pass a dict to read a JSON body.
    """
    raw = (source if source is not None else request.args).get(name, default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise BadRequest(f'{name} must be an integer')
    if lo is not None and value < lo:
        value = lo
    if hi is not None and value > hi:
        value = hi
    return value


def json_errors(bp):
    """Register JSON bodies for 400 and 404 raised inside `bp`."""
    @bp.errorhandler(BadRequest)
    def _bad_request(e):
        return jsonify(error=e.description or 'Bad request'), 400

    @bp.errorhandler(NotFound)
    def _not_found(e):
        return jsonify(error=e.description or 'Not found'), 404

    return bp
