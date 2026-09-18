import pytest

from admin_panel.views import PAGES

RULES = [rule for rule, _endpoint, _template in PAGES]

# A string that appears in this route's own template, and only that
# template - none of the other 7 site_admin_*.html files contain it,
# and in particular site_admin_security.html (the last PAGES entry)
# does not. That makes these markers a regression net against the
# late-binding-closure bug where every route would render whatever
# template PAGES ends with: if that bug reappears, requesting any
# route other than /site-admin/security returns security's body,
# which is missing that route's marker, and the assertion below fails.
PAGE_MARKERS = {
    "/site-admin": "TullSite Admin",
    "/site-admin/users": "<h1>// User Management</h1>",
    "/site-admin/logins": "<h1>// Login Monitor</h1>",
    "/site-admin/customers": "<h1>// Customer Management</h1>",
    "/site-admin/purchases": "<h1>// Purchase Management</h1>",
    "/site-admin/feedback": "<h1>// Feedback Management</h1>",
    "/site-admin/visitors": "<h1>// Visitor Analytics</h1>",
    "/site-admin/security": "<h1>// Security Dashboard</h1>",
}


def test_eight_pages_registered():
    assert len(PAGES) == 8


def test_page_markers_cover_every_route():
    # Guards the guard: PAGE_MARKERS must track PAGES 1:1 or the coverage
    # below is silently incomplete.
    assert set(PAGE_MARKERS) == set(RULES)


@pytest.mark.parametrize("rule", RULES)
def test_page_renders(client, rule):
    assert client.get(rule).status_code == 200


@pytest.mark.parametrize("rule", RULES)
def test_page_renders_its_own_template(client, rule):
    body = client.get(rule).data
    assert PAGE_MARKERS[rule].encode() in body


def test_dashboard_is_root_of_panel(client):
    assert client.get("/site-admin").status_code == 200


def test_nav_links_every_page(client):
    body = client.get("/site-admin").data
    for rule in RULES:
        assert f'href="{rule}"'.encode() in body


def test_active_page_marked(client):
    # /site-admin/users, not /site-admin/security: security is the last
    # PAGES entry, so probing it would still show class="active" under the
    # late-binding-closure bug (every route falls back to rendering AND
    # keying its nav state off the final PAGES entry). Probing a non-last
    # route, and requiring the active marker to land on THAT route's own
    # nav link, fails correctly if that bug reappears.
    body = client.get("/site-admin/users").data
    assert b'href="/site-admin/users" class="active"' in body


def test_no_fleet_server_chrome(client):
    # base.html must not carry fleet concepts into this app.
    body = client.get("/site-admin").data
    assert b"Fleet Server" not in body
    assert b"MQTT" not in body
    assert b"tull-format.js" not in body


def test_api_key_not_rendered(client):
    assert b"test-key" not in client.get("/site-admin").data
