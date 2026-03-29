from datetime import datetime, timezone
from werkzeug.security import generate_password_hash


def test_user_new_fields(db):
    from xissite.models import User
    user = User(
        email='patrick@tull.com',
        password=generate_password_hash('testpass123'),
        user_type='employee',
        status='active',
        display_name='Patrick T.',
        notes='Cofounder',
        failed_attempts=0,
    )
    db.session.add(user)
    db.session.commit()
    fetched = User.query.filter_by(email='patrick@tull.com').first()
    assert fetched.status == 'active'
    assert fetched.display_name == 'Patrick T.'
    assert fetched.failed_attempts == 0
    assert fetched.locked_until is None
    assert fetched.created_at is not None


def test_user_to_dict(db):
    from xissite.models import User
    user = User(
        email='jake@tull.com',
        password=generate_password_hash('testpass123'),
        user_type='admin',
        display_name='Jake R.',
    )
    db.session.add(user)
    db.session.commit()
    d = user.to_dict()
    assert d['email'] == 'jake@tull.com'
    assert d['user_type'] == 'admin'
    assert d['display_name'] == 'Jake R.'
    assert 'password' not in d


def test_login_attempt_model(db):
    from xissite.models import LoginAttempt
    attempt = LoginAttempt(
        ip_address='192.168.1.1',
        user_agent='Mozilla/5.0',
        username_attempted='admin',
        success=False,
        failure_reason='invalid_password',
    )
    db.session.add(attempt)
    db.session.commit()
    fetched = LoginAttempt.query.first()
    assert fetched.ip_address == '192.168.1.1'
    assert fetched.success is False
    assert fetched.to_dict()['username_attempted'] == 'admin'


def test_banned_ip_model(db):
    from xissite.models import BannedIP
    ban = BannedIP(
        ip_address='10.0.0.1',
        reason='Brute force',
        banned_by='auto',
        active=True,
    )
    db.session.add(ban)
    db.session.commit()
    fetched = BannedIP.query.first()
    assert fetched.active is True
    assert fetched.to_dict()['ip_address'] == '10.0.0.1'


def test_admin_audit_log_model(db):
    from xissite.models import AdminAuditLog
    entry = AdminAuditLog(
        action='user.create',
        target_type='user',
        target_id='5',
        admin_ip='127.0.0.1',
    )
    db.session.add(entry)
    db.session.commit()
    fetched = AdminAuditLog.query.first()
    assert fetched.action == 'user.create'
    assert fetched.to_dict()['target_type'] == 'user'


def test_feedback_new_fields(db):
    from xissite.models import FeedBack
    fb = FeedBack(
        feedbackmail='customer@example.com',
        feedbacktype='1',
        feedbackfullfield='Great product!',
        resolved=False,
    )
    db.session.add(fb)
    db.session.commit()
    fetched = FeedBack.query.first()
    assert fetched.resolved is False
    assert fetched.admin_notes is None
    assert fetched.to_dict()['feedbackmail'] == 'customer@example.com'
