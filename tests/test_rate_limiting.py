from werkzeug.security import generate_password_hash


def _create_admin(db):
    from xissite.models import User
    user = User(
        email='admin',
        password=generate_password_hash('correctpassword1'),
        user_type='admin',
        status='active',
    )
    db.session.add(user)
    db.session.commit()
    return user


def test_banned_ip_rejected(client, db):
    """Banned IPs are rejected before credential check."""
    from xissite.models import BannedIP
    _create_admin(db)
    ban = BannedIP(
        ip_address='127.0.0.1',
        reason='test ban',
        banned_by='test',
        active=True,
    )
    db.session.add(ban)
    db.session.commit()
    response = client.post('/login', data={
        'username': 'admin',
        'password': 'correctpassword1',
    }, follow_redirects=True)
    assert b'blocked' in response.data.lower() or b'banned' in response.data.lower()


def test_account_locks_after_5_failures(client, db):
    """Account locks after 5 consecutive failed attempts."""
    from xissite.models import User
    _create_admin(db)
    for _ in range(5):
        client.post('/login', data={
            'username': 'admin',
            'password': 'wrongpassword',
        })
    user = User.query.filter_by(email='admin').first()
    assert user.failed_attempts >= 5
    assert user.locked_until is not None


def test_successful_login_resets_lockout(client, db):
    """Successful login resets failed_attempts and locked_until."""
    from xissite.models import User
    user = _create_admin(db)
    user.failed_attempts = 3
    db.session.commit()
    client.post('/login', data={
        'username': 'admin',
        'password': 'correctpassword1',
    })
    user = User.query.filter_by(email='admin').first()
    assert user.failed_attempts == 0
    assert user.locked_until is None
