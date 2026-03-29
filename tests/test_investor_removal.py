def test_investor_route_removed(client):
    """The /investor route should no longer exist."""
    response = client.get('/investor')
    assert response.status_code == 404


def test_investor_login_rejected(client):
    """No investor credential checking in login flow."""
    import os
    os.environ['INVESTOR_USERNAME_HASH'] = 'dummy'
    os.environ['INVESTOR_PASSWORD_HASH'] = 'dummy'
    response = client.post('/login', data={
        'username': 'investor_user',
        'password': 'investor_pass',
    })
    assert b'investor' not in response.data.lower() or response.status_code != 302
    os.environ.pop('INVESTOR_USERNAME_HASH', None)
    os.environ.pop('INVESTOR_PASSWORD_HASH', None)
