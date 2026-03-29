"""Tests for dual auth on admin API (Bearer token + session)."""

import os
from werkzeug.security import generate_password_hash


API_KEY = os.environ.get('ADMIN_API_KEY', '')


def _create_admin(db):
    from xissite.models import User
    user = User(
        email='admin',
        password=generate_password_hash('adminpass1'),
        user_type='admin',
        status='active',
        display_name='Admin',
    )
    db.session.add(user)
    db.session.commit()
    return user


def _create_employee(db):
    from xissite.models import User
    user = User(
        email='employee',
        password=generate_password_hash('emppass1'),
        user_type='employee',
        status='active',
        display_name='Employee',
    )
    db.session.add(user)
    db.session.commit()
    return user


def _login(client, username, password):
    return client.post('/login', data={
        'username': username,
        'password': password,
    }, follow_redirects=False)


# ---------------------------------------------------------------------------
# Bearer token auth (TullOPS compatibility)
# ---------------------------------------------------------------------------

def test_bearer_token_auth(client, db):
    """Valid Bearer token grants access to admin API."""
    if not API_KEY:
        # No API key configured in test env; skip gracefully
        return
    _create_admin(db)
    resp = client.get('/api/admin/stats', headers={
        'Authorization': f'Bearer {API_KEY}',
    })
    assert resp.status_code == 200


def test_no_auth_rejected(client, db):
    """Unauthenticated requests are rejected."""
    resp = client.get('/api/admin/stats')
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Session auth
# ---------------------------------------------------------------------------

def test_admin_session_auth(client, db):
    """Admin session cookie grants access to admin API."""
    _create_admin(db)
    _login(client, 'admin', 'adminpass1')
    resp = client.get('/api/admin/stats')
    assert resp.status_code == 200


def test_employee_session_rejected(client, db):
    """Employee session does NOT grant access to admin API."""
    _create_employee(db)
    _login(client, 'employee', 'emppass1')
    resp = client.get('/api/admin/stats')
    assert resp.status_code == 401
