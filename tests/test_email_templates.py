"""Tests for email template generation."""

from xissite.email_templates import (
    contact_confirmation_html,
    admin_notification_html,
    feedback_reply_html,
    CATEGORY_COLORS,
)


def test_category_colors_has_four_entries():
    """CATEGORY_COLORS defines all 4 feedback categories."""
    assert len(CATEGORY_COLORS) == 4
    assert CATEGORY_COLORS['General'] == '#8B8B8B'
    assert CATEGORY_COLORS['Technical'] == '#F97316'
    assert CATEGORY_COLORS['Order'] == '#5bc0de'
    assert CATEGORY_COLORS['Feature'] == '#6ABD45'


def test_contact_confirmation_contains_ref_and_category():
    """Customer confirmation email includes ref number and category badge."""
    html = contact_confirmation_html('TULL-00001', 'Technical')
    assert 'TULL-00001' in html
    assert 'Technical' in html
    assert '#F97316' in html


def test_admin_notification_contains_deep_link():
    """Admin notification email includes a deep link to the feedback viewer."""

    class FakeFeedback:
        id = 42
        feedbackmail = 'user@example.com'
        feedbacktype = 'Feature'
        feedbackfullfield = 'Great product idea'
        feedbackorderid = None
        serial_number = None
        submitter_ip = '1.2.3.4'

    html = admin_notification_html(FakeFeedback(), 'TULL-00042', 'https://tullhydro.com')
    assert 'TULL-00042' in html
    assert 'feedbackview#feedback-42' in html or 'feedback-42' in html


def test_feedback_reply_contains_ref():
    """Reply email includes the reference number."""
    html = feedback_reply_html('Thanks for writing in!', 'TULL-00010', 'Order')
    assert 'TULL-00010' in html
    assert 'Thanks for writing in!' in html
