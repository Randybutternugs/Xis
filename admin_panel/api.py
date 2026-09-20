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
MUTATING = {"POST", "PUT", "DELETE"}


@bp.before_request
def refuse_cross_site_mutations():
    """The panel has no login, so a page in another browser tab could POST
    here and have the request forwarded with the real Bearer key.

    A custom header cannot be set by a cross-origin form or a "simple"
    fetch without a CORS preflight, and this app sends no CORS headers, so
    the preflight fails. base.html adds the header to every fetch(). The
    Origin check catches anything that somehow gets past that.
    """
    if request.method not in MUTATING:
        return None
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        return jsonify(error="Cross-site request refused"), 403
    origin = request.headers.get("Origin")
    if origin and origin.rstrip("/") != request.host_url.rstrip("/"):
        return jsonify(error="Cross-site request refused"), 403
    return None


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


@bp.route("/api/site-admin/export/<table>")
def export_csv(table):
    """CSV download. Registered before the catch-all: it needs an attachment
    header the generic passthrough does not add."""
    try:
        r = _upstream(f"export/{table}")
    except requests.Timeout:
        return jsonify(error="TullSite API timeout"), 504
    except requests.ConnectionError:
        return jsonify(error="TullSite API unreachable"), 502
    except requests.RequestException as e:
        return jsonify(error=str(e)), 502
    if r.status_code != 200:
        return jsonify(error="Export failed"), 502
    return Response(
        r.content,
        mimetype=r.headers.get("Content-Type", "text/csv"),
        headers={
            "Content-Disposition": f"attachment; filename=tullsite_{table}.csv"
        },
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
