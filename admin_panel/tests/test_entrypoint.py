from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent


def test_admin_panel_excluded_from_gae_deploy():
    text = (REPO / ".gcloudignore").read_text()
    lines = [line.strip() for line in text.split("\n")]

    # Assert admin_panel/ is explicitly listed
    assert "admin_panel/" in lines, (
        "admin_panel must not ship to App Engine — it runs on ARCS"
    )

    # Assert it is not negated (no !admin_panel/ or !admin_panel)
    negation_patterns = ["!admin_panel/", "!admin_panel"]
    for pattern in negation_patterns:
        assert pattern not in lines, (
            f"admin_panel exclusion must not be negated by {pattern}"
        )


def test_dev_artifacts_excluded_from_gae_deploy():
    """.gcloudignore has no #!include:.gitignore directive, so .gitignore
    entries (like .venv-admin/, .pytest_cache/, .remember/) do not apply to
    `gcloud app deploy` on their own — they must be listed here explicitly.
    """
    text = (REPO / ".gcloudignore").read_text()
    lines = [line.strip() for line in text.split("\n")]

    assert ".venv*/" in lines, (
        "the admin_panel dev virtualenv must not ship to App Engine"
    )
    assert ".pytest_cache/" in lines
    assert ".remember/" in lines


def test_local_secrets_excluded_from_gae_deploy():
    """vars.env holds the local secret key and API key; *.db is the local
    SQLite file with the local admin's password hash. Neither may ship."""
    text = (REPO / ".gcloudignore").read_text()
    lines = [line.strip() for line in text.split("\n")]
    assert "vars.env" in lines
    assert "*.db" in lines


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
