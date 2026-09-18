from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent


def test_admin_panel_excluded_from_gae_deploy():
    text = (REPO / ".gcloudignore").read_text()
    assert "admin_panel/" in text, (
        "admin_panel must not ship to App Engine — it runs on ARCS"
    )


def test_env_file_gitignored():
    text = (REPO / ".gitignore").read_text()
    assert "admin_panel.env" in text


def test_env_example_is_committed():
    assert (REPO / "admin_panel.env.example").exists()


def test_all_routes_registered(app):
    rules = {r.rule for r in app.url_map.iter_rules()}
    assert "/site-admin" in rules
    assert "/api/site-admin/<path:sub>" in rules
    assert "/api/site-admin/export/<table>" in rules
