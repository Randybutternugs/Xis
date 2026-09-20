"""Suspending or deleting an account must actually stop it.

Before: the login route skipped the suspended check for admins, the
user loader never looked at status (so a live session survived
suspension), PUT /users/<id> could soft-delete the bootstrap admin that
DELETE refuses to touch, and an admin could suspend or delete their own
account from the dashboard.
"""

import os

from werkzeug.security import generate_password_hash

os.environ['ADMIN_API_KEY'] = 'test-api-key-for-dual-auth'
API = {'Authorization': 'Bearer test-api-key-for-dual-auth'}


def _user(db, email, user_type, status='active'):
    from xissite.models import User
    u = User(email=email, password=generate_password_hash('password1234'),
             user_type=user_type, status=status, display_name=email)
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, email):
    return client.post('/login', data={'username': email, 'password': 'password1234'})


def _next_request():
    """Flask-Login caches the loaded user on ``g``. In production ``g`` is
    fresh for every request, but the test fixtures keep one app context
    open across requests, so drop the cache to simulate the next request."""
    from flask import g
    g.pop('_login_user', None)


def test_suspended_admin_cannot_log_in(client, db):
    _user(db, 'second-admin', 'admin', status='suspended')
    resp = _login(client, 'second-admin')
    assert resp.status_code == 200
    assert b'suspended' in resp.data.lower()


def test_bootstrap_admin_is_never_suspended(client, db):
    """The env-configured bootstrap account is the recovery path; the API
    refuses to suspend, soft-delete or change its status."""
    boot = _user(db, os.environ['ADMIN_BOOTSTRAP_EMAIL'], 'admin')
    assert client.post(f'/api/admin/users/{boot.id}/suspend', headers=API).status_code == 403
    assert client.put(f'/api/admin/users/{boot.id}', headers=API,
                      json={'status': 'deleted'}).status_code == 403
    assert client.put(f'/api/admin/users/{boot.id}', headers=API,
                      json={'status': 'suspended'}).status_code == 403
    assert client.delete(f'/api/admin/users/{boot.id}', headers=API).status_code == 403
    db.session.refresh(boot)
    assert boot.status == 'active'


def test_suspension_ends_a_live_session(client, db):
    emp = _user(db, 'emp', 'employee')
    assert _login(client, 'emp').status_code == 302
    assert client.get('/ops').status_code == 200
    assert client.post(f'/api/admin/users/{emp.id}/suspend', headers=API).status_code == 200
    _next_request()
    resp = client.get('/ops')
    assert resp.status_code == 302 and '/login' in resp.headers['Location']


def test_soft_delete_ends_a_live_session(client, db):
    emp = _user(db, 'emp', 'employee')
    _login(client, 'emp')
    assert client.delete(f'/api/admin/users/{emp.id}', headers=API).status_code == 200
    _next_request()
    assert client.get('/ops').status_code == 302


def test_admin_cannot_suspend_or_delete_self_from_dashboard(client, db, monkeypatch):
    me = _user(db, 'me', 'admin')
    _login(client, 'me')
    # Session path (no Bearer). Bypass the CSRF header check so a CSRF 403
    # cannot be mistaken for the self-protection 403 asserted here.
    import xissite.admin_api as api
    monkeypatch.setattr(api, 'validate_csrf', lambda token: None)
    for resp in (
        client.post(f'/api/admin/users/{me.id}/suspend'),
        client.delete(f'/api/admin/users/{me.id}'),
        client.put(f'/api/admin/users/{me.id}', json={'status': 'suspended'}),
    ):
        assert resp.status_code == 403
        assert 'own account' in resp.get_json()['error']
    db.session.refresh(me)
    assert me.status == 'active'
