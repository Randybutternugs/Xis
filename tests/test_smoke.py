def test_app_creates(app):
    """App factory returns a Flask app."""
    assert app is not None
    assert app.config['TESTING'] is True


def test_index_loads(client):
    """Public homepage returns 200."""
    response = client.get('/')
    assert response.status_code == 200
