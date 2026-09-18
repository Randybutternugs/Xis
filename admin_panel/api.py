"""Passthrough to the TullSite admin API.

The fleet-server original hand-wrote 40 wrapper routes plus a 280-line client
library. Their route table diffs 1:1 against TullSite's admin_api (31 paths,
no renames), so all of it collapses into one catch-all. New TullSite endpoints
work here with no change.

The API key stays server-side. That is the only reason this layer exists at
all — the browser must never hold it.
"""

import requests
from flask import Blueprint, Response, current_app, jsonify, request

bp = Blueprint("api", __name__)

TIMEOUT = 10
FORWARD_METHODS = ["GET", "POST", "PUT", "DELETE"]


def _upstream(path):
    """Forward the current request to <api_url>/api/admin/<path>."""
    cfg = current_app.config["PANEL"]
    return requests.request(
        request.method,
        f"{cfg.api_url}/api/admin/{path}",
        headers={"Authorization": f"Bearer {cfg.api_key}"},
        params=request.args,
        json=request.get_json(silent=True),
        timeout=TIMEOUT,
    )


@bp.route("/api/site-admin/<path:sub>", methods=FORWARD_METHODS)
def passthrough(sub):
    try:
        r = _upstream(sub)
    # Timeout FIRST: ConnectTimeout subclasses both Timeout and ConnectionError.
    except requests.Timeout:
        return jsonify(error="TullSite API timeout"), 504
    except requests.ConnectionError:
        return jsonify(error="TullSite API unreachable"), 502
    except requests.RequestException as e:
        return jsonify(error=str(e)), 502
    return Response(
        r.content,
        status=r.status_code,
        mimetype=r.headers.get("Content-Type", "application/json"),
    )
