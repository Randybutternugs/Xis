"""/api/admin/visitors/devices depends on the user-agents package, which
was never in requirements.txt, so the endpoint answered 500 everywhere."""

import os

os.environ['ADMIN_API_KEY'] = 'test-api-key-for-dual-auth'
API = {'Authorization': 'Bearer test-api-key-for-dual-auth'}


def test_devices_breakdown_parses_user_agents(client, db):
    from xissite.models import SiteVisit
    db.session.add(SiteVisit(
        ip_address='1.2.3.4', path='/',
        user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) '
                   'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    ))
    db.session.commit()
    resp = client.get('/api/admin/visitors/devices', headers=API)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['devices'][0]['name'] == 'Mobile'
    assert data['os'][0]['name'] == 'iOS'
