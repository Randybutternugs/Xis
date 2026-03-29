"""Tests for the contact/feedback form."""

import hashlib
import time
from unittest.mock import patch

from xissite.models import FeedBack


def _make_token(secret_key, offset_seconds=-5):
    """Generate a valid form_loaded_at token backdated by offset_seconds."""
    ts = str(int(time.time()) + offset_seconds)
    sig = hashlib.sha256(f"{ts}:{secret_key}".encode()).hexdigest()[:16]
    return f"{ts}:{sig}"


def test_contact_page_renders(client):
    """GET /contact returns 200 with all 4 feedback types."""
    resp = client.get('/contact')
    assert resp.status_code == 200
    html = resp.data.decode()
    assert 'General Inquiry' in html
    assert 'Technical Support' in html
    assert 'Order Related' in html
    assert 'Feature Request' in html


def test_contact_has_serial_number_field(client):
    """Contact form includes serial number placeholder."""
    resp = client.get('/contact')
    html = resp.data.decode()
    assert 'Found on your Tull Tower unit' in html


@patch('xissite.views.csrf.protect')
def test_contact_submit_creates_feedback(mock_csrf, client, db, app):
    """POST /contact with valid data creates a FeedBack record."""
    token = _make_token(app.config['SECRET_KEY'])
    resp = client.post('/contact', data={
        'feedbackemail': 'test@example.com',
        'feedbacktype': 'General',
        'feedbackfield': 'This is a test feedback message with enough characters.',
        'form_loaded_at': token,
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'submitted successfully' in resp.data

    fb = FeedBack.query.first()
    assert fb is not None
    assert fb.feedbackmail == 'test@example.com'
    assert fb.feedbacktype == 'General'


@patch('xissite.views.csrf.protect')
def test_contact_saves_serial_number(mock_csrf, client, db, app):
    """Submitted serial number is persisted to the database."""
    token = _make_token(app.config['SECRET_KEY'])
    client.post('/contact', data={
        'feedbackemail': 'test@example.com',
        'feedbacktype': 'Technical',
        'feedbackfield': 'Testing serial number persistence in the form.',
        'serialno': 'TT-V1-00042',
        'form_loaded_at': token,
    }, follow_redirects=True)

    fb = FeedBack.query.first()
    assert fb is not None
    assert fb.serial_number == 'TT-V1-00042'


@patch('xissite.views.csrf.protect')
def test_honeypot_blocks_bots(mock_csrf, client, db, app):
    """Filling the honeypot field prevents database save."""
    token = _make_token(app.config['SECRET_KEY'])
    client.post('/contact', data={
        'feedbackemail': 'bot@spammy.com',
        'feedbacktype': 'General',
        'feedbackfield': 'I am definitely a real person typing this message.',
        'website': 'http://spam-site.com',
        'form_loaded_at': token,
    }, follow_redirects=True)

    fb = FeedBack.query.first()
    assert fb is None
