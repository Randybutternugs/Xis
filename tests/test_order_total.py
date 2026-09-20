"""The order confirmation email must state what Stripe actually charged.

fulfill_order() emailed a hardcoded "$200" regardless of the session's
amount_total. The amount and currency are now taken from the Checkout
session and also stored on the purchase row.
"""

from unittest.mock import patch


def _session(amount_total=150000, currency='usd'):
    return {
        'customer_details': {
            'email': 'buyer@example.com', 'name': 'Buyer Person',
            'address': {'city': 'Austin', 'country': 'US', 'line1': '1 St',
                        'line2': None, 'postal_code': '78701', 'state': 'TX'},
        },
        'payment_status': 'paid',
        'amount_total': amount_total,
        'currency': currency,
    }


def test_confirmation_email_states_the_charged_amount(client, db, monkeypatch):
    from xissite import sales
    monkeypatch.setenv('POSTMARK_SERVER_TOKEN', 'x')
    monkeypatch.setenv('POSTMARK_SENDER_EMAIL', 's@t.co')
    with patch('xissite.sales.requests.post') as post:
        post.return_value.status_code = 200
        sales.fulfill_order(_session())
    body = post.call_args.kwargs['json']['HtmlBody']
    assert '$1,500.00' in body
    assert '$200' not in body


def test_confirmation_email_shows_non_usd_with_currency_code(client, db, monkeypatch):
    from xissite import sales
    monkeypatch.setenv('POSTMARK_SERVER_TOKEN', 'x')
    monkeypatch.setenv('POSTMARK_SENDER_EMAIL', 's@t.co')
    with patch('xissite.sales.requests.post') as post:
        post.return_value.status_code = 200
        sales.fulfill_order(_session(amount_total=199999, currency='cad'))
    assert '1,999.99 CAD' in post.call_args.kwargs['json']['HtmlBody']


def test_purchase_row_records_amount_and_currency(client, db):
    from xissite import sales
    from xissite.models import Purchase_info
    sales.create_order(_session())
    p = Purchase_info.query.first()
    assert p.amount_cents == 150000
    assert p.currency == 'usd'
    assert p.to_dict()['amount_cents'] == 150000


def test_missing_amount_is_tolerated(client, db, monkeypatch):
    """Older webhook payloads or test events may omit amount_total."""
    from xissite import sales
    from xissite.models import Purchase_info
    s = _session()
    del s['amount_total']
    del s['currency']
    sales.create_order(s)
    assert Purchase_info.query.first().amount_cents is None
    monkeypatch.setenv('POSTMARK_SERVER_TOKEN', 'x')
    monkeypatch.setenv('POSTMARK_SENDER_EMAIL', 's@t.co')
    with patch('xissite.sales.requests.post') as post:
        post.return_value.status_code = 200
        sales.fulfill_order(s)
    body = post.call_args.kwargs['json']['HtmlBody']
    assert 'see your Stripe receipt' in body
    assert '$' not in body
