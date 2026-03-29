from werkzeug.security import generate_password_hash


def _create_admin(db):
    from xissite.models import User
    user = User(
        email='admin',
        password=generate_password_hash('correctpassword1'),
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
        email='patrick',
        password=generate_password_hash('patrickpass11'),
        user_type='employee',
        status='active',
        display_name='Patrick T.',
    )
    db.session.add(user)
    db.session.commit()
    return user


def test_login_page_loads(client):
    response = client.get('/login')
    assert response.status_code == 200
    assert b'login' in response.data.lower()


def test_login_valid_admin(client, db):
    _create_admin(db)
    response = client.post('/login', data={
        'username': 'admin',
        'password': 'correctpassword1',
    }, follow_redirects=False)
    assert response.status_code == 302
    assert '/viewdb' in response.headers['Location']


def test_login_valid_employee(client, db):
    _create_employee(db)
    response = client.post('/login', data={
        'username': 'patrick',
        'password': 'patrickpass11',
    }, follow_redirects=False)
    assert response.status_code == 302


def test_login_invalid_password(client, db):
    _create_admin(db)
    response = client.post('/login', data={
        'username': 'admin',
        'password': 'wrongpassword',
    }, follow_redirects=True)
    assert b'Invalid credentials' in response.data


def test_login_nonexistent_user(client, db):
    response = client.post('/login', data={
        'username': 'nobody',
        'password': 'somepassword',
    }, follow_redirects=True)
    assert b'Invalid credentials' in response.data


def test_login_suspended_user(client, db):
    user = _create_admin(db)
    user.status = 'suspended'
    db.session.commit()
    response = client.post('/login', data={
        'username': 'admin',
        'password': 'correctpassword1',
    }, follow_redirects=True)
    assert b'suspended' in response.data.lower() or b'Invalid' in response.data


def test_login_records_attempt(client, db):
    from xissite.models import LoginAttempt
    _create_admin(db)
    client.post('/login', data={
        'username': 'admin',
        'password': 'wrongpassword',
    })
    attempts = LoginAttempt.query.all()
    assert len(attempts) == 1
    assert attempts[0].success is False
    assert attempts[0].username_attempted == 'admin'


def test_login_updates_last_login(client, db):
    from xissite.models import User
    _create_admin(db)
    client.post('/login', data={
        'username': 'admin',
        'password': 'correctpassword1',
    })
    user = User.query.filter_by(email='admin').first()
    assert user.last_login is not None
