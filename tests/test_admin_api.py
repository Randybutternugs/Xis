def test_admin_api_health(client):
    """Admin API health endpoint returns 200 without auth."""
    response = client.get('/api/admin/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'ok'


def test_admin_api_requires_auth(client):
    """Admin API endpoints return 401 without Bearer token."""
    response = client.get('/api/admin/stats')
    assert response.status_code in (401, 503)
