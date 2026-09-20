"""The panel has no login, so a page in another tab could POST to it.

Browsers send body-less POSTs cross-origin without a CORS preflight, and
the passthrough would forward them with the real Bearer key. Two checks
close that: every mutating request must carry a custom header (which a
cross-origin form or simple fetch cannot add without a preflight that
fails), and an Origin header, when present, must match the panel itself.
"""

import pytest

XHR = {"X-Requested-With": "XMLHttpRequest"}


@pytest.mark.parametrize("method", ["post", "put", "delete"])
def test_mutation_without_custom_header_is_refused(client, capture_upstream, method):
    resp = getattr(client, method)("/api/site-admin/users/1/suspend")
    assert resp.status_code == 403
    assert "url" not in capture_upstream, "request must not reach upstream"


@pytest.mark.parametrize("method", ["post", "put", "delete"])
def test_mutation_with_custom_header_is_forwarded(client, capture_upstream, method):
    resp = getattr(client, method)("/api/site-admin/users/1/suspend", headers=XHR)
    assert resp.status_code == 200
    assert capture_upstream["url"].endswith("/api/admin/users/1/suspend")


def test_get_needs_no_header(client, capture_upstream):
    resp = client.get("/api/site-admin/stats")
    assert resp.status_code == 200


def test_foreign_origin_is_refused_even_with_header(client, capture_upstream):
    resp = client.post(
        "/api/site-admin/users/1/suspend",
        headers={**XHR, "Origin": "https://evil.example"},
    )
    assert resp.status_code == 403
    assert "url" not in capture_upstream


def test_own_origin_is_accepted(client, capture_upstream):
    resp = client.post(
        "/api/site-admin/users/1/suspend",
        headers={**XHR, "Origin": "http://localhost"},
    )
    assert resp.status_code == 200


def test_pages_send_the_header_on_every_request():
    """base.html wraps fetch() so every same-origin call carries the header;
    without this, the guard above would break the panel's own UI."""
    from pathlib import Path
    base = Path(__file__).resolve().parent.parent / "templates" / "base.html"
    assert "X-Requested-With" in base.read_text(encoding="utf-8")
