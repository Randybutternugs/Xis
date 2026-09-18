import pytest

from admin_panel.views import PAGES

RULES = [rule for rule, _endpoint, _template in PAGES]


def test_eight_pages_registered():
    assert len(PAGES) == 8


@pytest.mark.parametrize("rule", RULES)
def test_page_renders(client, rule):
    assert client.get(rule).status_code == 200


def test_dashboard_is_root_of_panel(client):
    assert client.get("/site-admin").status_code == 200


def test_nav_links_every_page(client):
    body = client.get("/site-admin").data
    for rule in RULES:
        assert f'href="{rule}"'.encode() in body


def test_active_page_marked(client):
    body = client.get("/site-admin/security").data
    assert b'class="active"' in body


def test_no_fleet_server_chrome(client):
    # base.html must not carry fleet concepts into this app.
    body = client.get("/site-admin").data
    assert b"Fleet Server" not in body
    assert b"MQTT" not in body
    assert b"tull-format.js" not in body


def test_api_key_not_rendered(client):
    assert b"test-key" not in client.get("/site-admin").data
