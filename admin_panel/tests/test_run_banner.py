"""The startup banner must print on a legacy Windows console.

ARCS runs Windows. When stdout is redirected to a file, or the console is
on the default code page, Python encodes prints as cp1252, and any
non-ASCII glyph in the banner raises UnicodeEncodeError before app.run()
is ever reached. The panel then exits 1 with no server listening.
"""

from unittest.mock import MagicMock

import pytest

from admin_panel import run as run_module


@pytest.fixture
def no_server(monkeypatch):
    """Replace create_app so main() prints its banner without binding a port."""
    fake_app = MagicMock()
    monkeypatch.setattr(run_module, "create_app", lambda cfg: fake_app)
    return fake_app


@pytest.mark.parametrize("host", ["127.0.0.1", "0.0.0.0"])
def test_banner_is_cp1252_safe(monkeypatch, capsys, no_server, host):
    monkeypatch.setenv("ADMIN_API_KEY", "k")
    monkeypatch.setenv("ADMIN_PANEL_HOST", host)

    run_module.main()

    out = capsys.readouterr().out
    assert "TULL SITE ADMIN PANEL" in out
    assert no_server.run.called, "app.run() must be reached after the banner"
    # A redirected Windows console encodes as cp1252 with errors='strict'.
    out.encode("cp1252")
