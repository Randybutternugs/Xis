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
