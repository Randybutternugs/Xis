"""Datetimes loaded from SQLite come back naive; comparing them to
datetime.now(timezone.utc) raises TypeError. These tests reload rows the
way a real second request would (expire_all) and hit the paths that
compare or subtract those values.
"""

import os
from datetime import datetime, timedelta, timezone

from werkzeug.security import generate_password_hash

os.environ['ADMIN_API_KEY'] = 'test-api-key-for-dual-auth'
API = {'Authorization': 'Bearer test-api-key-for-dual-auth'}


def _employee(db, **extra):
    from xissite.models import User
    user = User(
        email='emp',
        password=generate_password_hash('emppass1234'),
        user_type='employee',
        status='active',
        **extra,
    )
    db.session.add(user)
    db.session.commit()
    db.session.expire_all()
    return user


def test_locked_account_login_is_rejected_not_crashed(client, db):
    _employee(db, locked_until=datetime.now(timezone.utc) + timedelta(minutes=15))
    resp = client.post('/login', data={'username': 'emp', 'password': 'emppass1234'})
    assert resp.status_code == 200
    assert b'locked' in resp.data.lower()


def test_expiring_ip_ban_login_is_blocked_not_crashed(client, db):
    from xissite.models import BannedIP
    _employee(db)
    db.session.add(BannedIP(
        ip_address='127.0.0.1', reason='t', banned_by='test', active=True,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    ))
    db.session.commit()
    db.session.expire_all()
    resp = client.post('/login', data={'username': 'emp', 'password': 'x'})
    assert resp.status_code == 200
    assert b'blocked' in resp.data.lower()


def test_expired_ip_ban_is_lifted(client, db):
    from xissite.models import BannedIP
    _employee(db)
    db.session.add(BannedIP(
        ip_address='127.0.0.1', reason='t', banned_by='test', active=True,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    ))
    db.session.commit()
    db.session.expire_all()
    resp = client.post('/login', data={'username': 'emp', 'password': 'emppass1234'})
    assert resp.status_code == 302, 'expired ban must not block a valid login'
    assert BannedIP.query.filter_by(active=True).count() == 0


def _feedback(db):
    from xissite.models import FeedBack
    fb = FeedBack(feedbackmail='a@b.co', feedbacktype='General',
                  feedbackfullfield='hello there friend')
    db.session.add(fb)
    db.session.commit()
    fid = fb.id
    db.session.expire_all()
    return fid


def test_feedback_stats_ages_unresolved_rows(client, db):
    _feedback(db)
    resp = client.get('/api/admin/feedback/stats', headers=API)
    assert resp.status_code == 200
    assert resp.get_json()['aging_buckets']['under_3d'] == 1


def test_feedback_resolve_computes_resolution_hours(client, db):
    fid = _feedback(db)
    resp = client.put(f'/api/admin/feedback/{fid}', headers=API, json={'resolved': True})
    assert resp.status_code == 200
    assert resp.get_json()['resolution_time_hours'] == 1


def test_feedback_reply_with_resolve_computes_resolution_hours(client, db, monkeypatch):
    monkeypatch.delenv('POSTMARK_SERVER_TOKEN', raising=False)
    fid = _feedback(db)
    # Postmark unset -> 503 before any date arithmetic; set a dummy token and
    # stub the outbound call so the resolve branch runs.
    monkeypatch.setenv('POSTMARK_SERVER_TOKEN', 'x')
    monkeypatch.setenv('POSTMARK_SENDER_EMAIL', 's@t.co')
    import requests

    class _R:
        status_code = 200
    monkeypatch.setattr(requests, 'post', lambda *a, **k: _R())
    resp = client.post(f'/api/admin/feedback/{fid}/reply', headers=API,
                       json={'message': 'hi', 'resolve': True})
    assert resp.status_code == 200
    assert resp.get_json()['feedback']['resolution_time_hours'] == 1
