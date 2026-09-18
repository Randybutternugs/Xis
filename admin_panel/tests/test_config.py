import pytest

from admin_panel.config import DEFAULT_API_URL, Config


def test_from_env_reads_key(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    cfg = Config.from_env()
    assert cfg.api_key == "secret"


def test_from_env_defaults(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    monkeypatch.delenv("TULLSITE_API_URL", raising=False)
    monkeypatch.delenv("ADMIN_PANEL_HOST", raising=False)
    monkeypatch.delenv("ADMIN_PANEL_PORT", raising=False)
    cfg = Config.from_env()
    assert cfg.api_url == DEFAULT_API_URL
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 5002


def test_admin_panel_host_opt_in(monkeypatch):
    """Verify that ADMIN_PANEL_HOST=0.0.0.0 opt-in still works."""
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    monkeypatch.setenv("ADMIN_PANEL_HOST", "0.0.0.0")
    cfg = Config.from_env()
    assert cfg.host == "0.0.0.0"


def test_admin_panel_host_blank_falls_back_to_default(monkeypatch):
    """Blanking the value (not deleting it) must still yield loopback.

    ADMIN_PANEL_HOST="" is what an operator gets by blanking the line in
    admin_panel.env rather than deleting it. os.environ.get(key, default)
    only falls back when the key is absent, so an empty string previously
    slipped through to app.run(host=""), which binds every interface.
    """
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    monkeypatch.setenv("ADMIN_PANEL_HOST", "")
    cfg = Config.from_env()
    assert cfg.host == "127.0.0.1"


def test_admin_panel_host_whitespace_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    monkeypatch.setenv("ADMIN_PANEL_HOST", "   ")
    cfg = Config.from_env()
    assert cfg.host == "127.0.0.1"


def test_admin_panel_port_blank_falls_back_to_default(monkeypatch):
    """Same empty-string trap applies to the port: blanking the line must
    fall back to DEFAULT_PORT rather than raising ValueError out of int("").
    """
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    monkeypatch.setenv("ADMIN_PANEL_PORT", "")
    cfg = Config.from_env()
    assert cfg.port == 5002


def test_admin_panel_port_whitespace_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    monkeypatch.setenv("ADMIN_PANEL_PORT", "   ")
    cfg = Config.from_env()
    assert cfg.port == 5002


def test_trailing_slash_stripped(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    monkeypatch.setenv("TULLSITE_API_URL", "https://example.test/")
    assert Config.from_env().api_url == "https://example.test"


def test_missing_key_refuses_to_start(monkeypatch):
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    with pytest.raises(RuntimeError) as exc:
        Config.from_env()
    assert "ADMIN_API_KEY" in str(exc.value)


def test_blank_key_refuses_to_start(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "   ")
    with pytest.raises(RuntimeError):
        Config.from_env()
