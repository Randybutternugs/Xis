"""Bad query parameters and failed side effects must surface as 4xx or an
honest response, never as a 500 or a false success."""

import os
from unittest.mock import patch

import pytest

os.environ['ADMIN_API_KEY'] = 'test-api-key-for-dual-auth'
API = {'Authorization': 'Bearer test-api-key-for-dual-auth'}


@pytest.mark.parametrize('path', [
    '/api/admin/login-attempts?limit=abc',
    '/api/admin/customers?limit=x&offset=y',
    '/api/admin/purchases?limit=z',
    '/api/admin/purchases?customer_id=nope',
    '/api/admin/visitors?days=abc',
    '/api/admin/visitors/recent?limit=abc',
    '/api/admin/security/login-heatmap?days=abc',
    '/api/admin/security/audit-log?limit=abc',
    '/api/admin/visitors/devices?days=abc',
    '/api/admin/visitors/referrers?days=abc',
    '/api/admin/visitors/heatmap?days=abc',
    '/api/admin/visitors/pageflow?days=abc',
    '/api/admin/purchases/stats?days=abc',
    '/api/admin/purchases/funnel?days=abc',
])
def test_non_numeric_params_are_400_not_500(client, db, path):
    resp = client.get(path, headers=API)
    assert resp.status_code == 400, f'{path} -> {resp.status_code}'
    assert 'error' in resp.get_json()


def test_days_is_clamped_to_a_sane_range(client, db):
    resp = client.get('/api/admin/visitors?days=999999999', headers=API)
    assert resp.status_code == 200
    assert resp.get_json()['days'] <= 365


def test_ban_ip_rejects_non_numeric_expiry(client, db):
    resp = client.post('/api/admin/banned-ips', headers=API,
                       json={'ip_address': '5.5.5.5', 'expires_hours': 'soon'})
    assert resp.status_code == 400


def test_reply_reports_failure_when_email_does_not_send(client, db, monkeypatch):
    from xissite.models import FeedBack
    fb = FeedBack(feedbackmail='a@b.co', feedbacktype='General', feedbackfullfield='hello there friend')
    db.session.add(fb)
    db.session.commit()
    monkeypatch.setenv('POSTMARK_SERVER_TOKEN', 'x')
    monkeypatch.setenv('POSTMARK_SENDER_EMAIL', 's@t.co')
    with patch('requests.post') as post:
        post.return_value.status_code = 422
        resp = client.post(f'/api/admin/feedback/{fb.id}/reply', headers=API, json={'message': 'hi'})
    assert resp.status_code == 502
    body = resp.get_json()
    assert body['ok'] is False and body['email_sent'] is False


def test_reply_refuses_without_sender_address(client, db, monkeypatch):
    from xissite.models import FeedBack
    fb = FeedBack(feedbackmail='a@b.co', feedbacktype='General', feedbackfullfield='hello there friend')
    db.session.add(fb)
    db.session.commit()
    monkeypatch.setenv('POSTMARK_SERVER_TOKEN', 'x')
    monkeypatch.delenv('POSTMARK_SENDER_EMAIL', raising=False)
    resp = client.post(f'/api/admin/feedback/{fb.id}/reply', headers=API, json={'message': 'hi'})
    assert resp.status_code == 503


def test_resolve_geo_reports_lookup_failure_instead_of_dropping_the_ip(client, db):
    with patch('requests.get') as get:
        get.return_value.ok = False
        get.return_value.status_code = 429
        resp = client.post('/api/admin/security/resolve-geo', headers=API, json={'ips': ['8.8.8.8']})
    assert resp.status_code == 200
    assert resp.get_json()['8.8.8.8']['country'] == 'Lookup failed'
