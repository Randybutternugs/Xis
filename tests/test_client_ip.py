"""One rule for the client address: remote_addr, never X-Forwarded-For.

App Engine sets remote_addr to the real client. The X-Forwarded-For header
can be supplied by the client itself, and two code paths trusted its first
value: the contact form's spam rate limit and the ban endpoint's "cannot
ban yourself" check.
"""

import hashlib
import os
import time
from unittest.mock import patch

os.environ['ADMIN_API_KEY'] = 'test-api-key-for-dual-auth'
API = {'Authorization': 'Bearer test-api-key-for-dual-auth'}


def _aged_token(secret, age=10):
    """A signed form-load token from `age` seconds ago, so the too-fast check passes."""
    ts = str(int(time.time()) - age)
    return f"{ts}:{hashlib.sha256(f'{ts}:{secret}'.encode()).hexdigest()[:16]}"


@patch('xissite.views.csrf.protect')
def test_contact_records_remote_addr_not_spoofed_header(mock_csrf, client, db, app):
    from xissite.models import FeedBack
    client.post('/contact', data={
        'feedbackemail': 'test@example.com',
        'feedbacktype': 'General',
        'feedbackfield': 'This is a test feedback message with enough characters.',
        'form_loaded_at': _aged_token(app.config['SECRET_KEY']),
    }, headers={'X-Forwarded-For': '203.0.113.9, 10.0.0.1'})
    fb = FeedBack.query.first()
    assert fb is not None
    assert fb.submitter_ip == '127.0.0.1'


def test_ban_ip_self_check_uses_remote_addr(client, db):
    # Spoofing the header must not let a caller dodge the self-ban guard,
    # and must not make an unrelated address look like the caller's own.
    resp = client.post('/api/admin/banned-ips', headers={**API, 'X-Forwarded-For': '5.5.5.5'},
                       json={'ip_address': '5.5.5.5'})
    assert resp.status_code == 201, resp.get_json()
    resp = client.post('/api/admin/banned-ips', headers={**API, 'X-Forwarded-For': '5.5.5.6'},
                       json={'ip_address': '127.0.0.1'})
    assert resp.status_code == 400
