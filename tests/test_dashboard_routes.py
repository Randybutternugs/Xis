"""Tests for admin dashboard and employee ops route access control."""

from werkzeug.security import generate_password_hash


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
# /admin route
# ---------------------------------------------------------------------------

def test_admin_dashboard_requires_auth(client, db):
    """Anonymous users get redirected to login."""
    resp = client.get('/admin', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_admin_dashboard_admin_access(client, db):
    """Admin users can access the dashboard."""
    _create_admin(db)
    _login(client, 'admin', 'adminpass1')
    resp = client.get('/admin')
    assert resp.status_code == 200
    assert b'ADMIN DASHBOARD' in resp.data


def test_admin_dashboard_employee_denied(client, db):
    """Employee users are redirected away from admin dashboard."""
    _create_employee(db)
    _login(client, 'employee', 'emppass1')
    resp = client.get('/admin', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


# ---------------------------------------------------------------------------
# /ops route
# ---------------------------------------------------------------------------

def test_ops_requires_auth(client, db):
    """Anonymous users get redirected to login."""
    resp = client.get('/ops', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_ops_employee_access(client, db):
    """Employee users can access operations center."""
    _create_employee(db)
    _login(client, 'employee', 'emppass1')
    resp = client.get('/ops')
    assert resp.status_code == 200
    assert b'OPERATIONS' in resp.data


def test_ops_admin_access(client, db):
    """Admin users can also access operations center."""
    _create_admin(db)
    _login(client, 'admin', 'adminpass1')
    resp = client.get('/ops')
    assert resp.status_code == 200
    assert b'OPERATIONS' in resp.data


# ---------------------------------------------------------------------------
# Login redirect targets
# ---------------------------------------------------------------------------

def test_admin_login_redirects_to_admin(client, db):
    """Admin login redirects to /admin."""
    _create_admin(db)
    resp = _login(client, 'admin', 'adminpass1')
    assert resp.status_code == 302
    assert '/admin' in resp.headers['Location']


def test_employee_login_redirects_to_ops(client, db):
    """Employee login redirects to /ops."""
    _create_employee(db)
    resp = _login(client, 'employee', 'emppass1')
    assert resp.status_code == 302
    assert '/ops' in resp.headers['Location']


# ---------------------------------------------------------------------------
# /viewdb backward compatibility
# ---------------------------------------------------------------------------

def test_viewdb_still_works_for_admin(client, db):
    """Legacy /viewdb route still accessible to admin."""
    _create_admin(db)
    _login(client, 'admin', 'adminpass1')
    resp = client.get('/viewdb')
    assert resp.status_code == 200
