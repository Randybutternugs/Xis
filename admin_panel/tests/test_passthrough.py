import requests

from admin_panel.tests.conftest import FakeResponse


def test_get_maps_path_to_upstream(client, capture_upstream):
    client.get("/api/site-admin/customers")
    assert capture_upstream["url"] == "https://upstream.test/api/admin/customers"
    assert capture_upstream["method"] == "GET"


def test_nested_path_preserved(client, capture_upstream):
    client.get("/api/site-admin/security/login-heatmap")
    assert capture_upstream["url"] == (
        "https://upstream.test/api/admin/security/login-heatmap"
    )


def test_bearer_header_sent(client, capture_upstream):
    client.get("/api/site-admin/stats")
    assert capture_upstream["headers"]["Authorization"] == "Bearer test-key"


def test_query_params_forwarded(client, capture_upstream):
    client.get("/api/site-admin/users?status=active&user_type=admin")
    assert capture_upstream["params"]["status"] == "active"
    assert capture_upstream["params"]["user_type"] == "admin"


def test_json_body_forwarded(client, capture_upstream):
    client.post("/api/site-admin/users", json={"email": "a@b.c"})
    assert capture_upstream["json"] == {"email": "a@b.c"}


def test_put_and_delete_allowed(client, capture_upstream):
    assert client.put("/api/site-admin/users/1", json={}).status_code == 200
    assert client.delete("/api/site-admin/users/1").status_code == 200


def test_timeout_is_ten_seconds(client, capture_upstream):
    client.get("/api/site-admin/stats")
    assert capture_upstream["timeout"] == 10


def test_upstream_status_forwarded(client, capture_upstream):
    capture_upstream["response"] = FakeResponse(b'{"error":"nope"}', 401)
    resp = client.get("/api/site-admin/stats")
    assert resp.status_code == 401
    assert b"nope" in resp.data


def test_connection_error_is_502(client, capture_upstream):
    capture_upstream["response"] = requests.ConnectionError()
    resp = client.get("/api/site-admin/stats")
    assert resp.status_code == 502
    assert b"unreachable" in resp.data


def test_timeout_is_504(client, capture_upstream):
    capture_upstream["response"] = requests.Timeout()
    resp = client.get("/api/site-admin/stats")
    assert resp.status_code == 504
    assert b"timeout" in resp.data


def test_connect_timeout_reports_504_not_502(client, capture_upstream):
    # ConnectTimeout subclasses BOTH ConnectionError and Timeout. Catching
    # ConnectionError first would misreport it as 502.
    capture_upstream["response"] = requests.exceptions.ConnectTimeout()
    assert client.get("/api/site-admin/stats").status_code == 504


def test_api_key_never_reaches_the_browser(client, capture_upstream):
    resp = client.get("/api/site-admin/stats")
    assert b"test-key" not in resp.data
