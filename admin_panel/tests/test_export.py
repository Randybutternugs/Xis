import requests

from admin_panel.tests.conftest import FakeResponse


def test_export_sets_attachment_filename(client, capture_upstream):
    capture_upstream["response"] = FakeResponse(
        b"id,email\n1,a@b.c\n", 200, {"Content-Type": "text/csv"}
    )
    resp = client.get("/api/site-admin/export/customers")
    assert resp.status_code == 200
    assert resp.headers["Content-Disposition"] == (
        "attachment; filename=tullsite_customers.csv"
    )


def test_export_forwards_csv_body(client, capture_upstream):
    capture_upstream["response"] = FakeResponse(
        b"id,email\n1,a@b.c\n", 200, {"Content-Type": "text/csv"}
    )
    resp = client.get("/api/site-admin/export/customers")
    assert resp.data == b"id,email\n1,a@b.c\n"
    assert "text/csv" in resp.headers["Content-Type"]


def test_export_hits_upstream_export_path(client, capture_upstream):
    capture_upstream["response"] = FakeResponse(b"", 200, {"Content-Type": "text/csv"})
    client.get("/api/site-admin/export/purchases")
    assert capture_upstream["url"] == (
        "https://upstream.test/api/admin/export/purchases"
    )


def test_export_upstream_failure_is_502(client, capture_upstream):
    capture_upstream["response"] = FakeResponse(b'{"error":"bad"}', 500)
    resp = client.get("/api/site-admin/export/customers")
    assert resp.status_code == 502
    assert b"Export failed" in resp.data


def test_export_timeout_is_504(client, capture_upstream):
    capture_upstream["response"] = requests.Timeout()
    assert client.get("/api/site-admin/export/customers").status_code == 504
