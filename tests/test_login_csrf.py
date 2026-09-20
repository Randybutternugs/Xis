"""The login form carries a CSRF token; the route must actually check it.

The route used to read request.form directly and never call
validate_on_submit(), so the token in the template was decorative. This
test builds an app with CSRF enabled (the shared fixture disables it).
"""

import re

from werkzeug.security import generate_password_hash


def _csrf_app(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///:memory:')
    from xissite import create_app, db
    app = create_app()
    app.config['TESTING'] = True
    assert app.config.get('WTF_CSRF_ENABLED', True) is True
    with app.app_context():
        from xissite.models import User
        db.create_all()
        db.session.add(User(email='emp', password=generate_password_hash('password1234'),
                            user_type='employee', status='active'))
        db.session.commit()
    return app, db


def test_login_without_csrf_token_is_rejected(monkeypatch):
    app, db = _csrf_app(monkeypatch)
    client = app.test_client()
    resp = client.post('/login', data={'username': 'emp', 'password': 'password1234'})
    assert resp.status_code == 200, 'no redirect: login must not succeed'
    with app.app_context():
        from xissite.models import LoginAttempt
        assert LoginAttempt.query.count() == 0, 'a rejected form must not count as an attempt'
    assert client.get('/ops').status_code == 302


def test_login_with_csrf_token_succeeds(monkeypatch):
    app, db = _csrf_app(monkeypatch)
    client = app.test_client()
    page = client.get('/login').data.decode()
    token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page).group(1)
    resp = client.post('/login', data={'username': 'emp', 'password': 'password1234',
                                       'csrf_token': token})
    assert resp.status_code == 302 and resp.headers['Location'].endswith('/ops')
