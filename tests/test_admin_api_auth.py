import os
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash


def _auth_header():
    api_key = os.environ.get('ADMIN_API_KEY', 'test-api-key')
    os.environ['ADMIN_API_KEY'] = api_key
    return {'Authorization': f'Bearer {api_key}'}


def test_activate_resets_lockout(client, db):
    from xissite.models import User
    user = User(
        email='locked_user',
        password=generate_password_hash('testpassword1'),
        user_type='employee',
        status='suspended',
        failed_attempts=10,
        locked_until=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.session.add(user)
    db.session.commit()
    response = client.post(
        f'/api/admin/users/{user.id}/activate',
        headers=_auth_header(),
    )
    assert response.status_code == 200
    refreshed = User.query.get(user.id)
    assert refreshed.status == 'active'
    assert refreshed.failed_attempts == 0
    assert refreshed.locked_until is None


def test_create_user_password_too_short(client, db):
    response = client.post(
        '/api/admin/users',
        headers=_auth_header(),
        json={
            'email': 'newuser@tull.com',
            'password': 'short',
            'user_type': 'employee',
        },
    )
    assert response.status_code == 400
    assert 'password' in response.get_json().get('error', '').lower()


def test_create_user_valid(client, db):
    response = client.post(
        '/api/admin/users',
        headers=_auth_header(),
        json={
            'email': 'newuser@tull.com',
            'password': 'validpassword123',
            'user_type': 'employee',
        },
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data['email'] == 'newuser@tull.com'
    assert data['user_type'] == 'employee'
