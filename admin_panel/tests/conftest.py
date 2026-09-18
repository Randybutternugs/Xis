import os

import pytest

# Set before any admin_panel import so Config.from_env() succeeds.
os.environ.setdefault("ADMIN_API_KEY", "test-key")
os.environ.setdefault("TULLSITE_API_URL", "https://upstream.test")


@pytest.fixture
def app():
    from admin_panel import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


class FakeResponse:
    """Stands in for requests.Response in passthrough tests."""

    def __init__(self, content=b"{}", status_code=200, headers=None):
        self.content = content
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "application/json"}


@pytest.fixture
def capture_upstream(monkeypatch):
    """Patch requests.request and record the call it received.

    Returns a dict that fills in with keys: method, url, headers, params, json.
    Assign to `calls["response"]` before the request to control what comes back.
    """
    calls = {"response": FakeResponse()}

    def fake_request(method, url, **kwargs):
        calls["method"] = method
        calls["url"] = url
        calls["headers"] = kwargs.get("headers")
        calls["params"] = kwargs.get("params")
        calls["json"] = kwargs.get("json")
        calls["timeout"] = kwargs.get("timeout")
        result = calls["response"]
        if isinstance(result, Exception):
            raise result
        return result

    import admin_panel.api

    monkeypatch.setattr(admin_panel.api.requests, "request", fake_request)
    return calls
