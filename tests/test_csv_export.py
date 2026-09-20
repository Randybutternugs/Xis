"""CSV exports are opened in Excel or Sheets. A cell beginning with = + - @
is executed as a formula there, and every exported string column comes
from a customer, a contact form or a login attempt."""

import csv
import io
import os

os.environ['ADMIN_API_KEY'] = 'test-api-key-for-dual-auth'
API = {'Authorization': 'Bearer test-api-key-for-dual-auth'}


def _rows(resp):
    return list(csv.reader(io.StringIO(resp.data.decode('utf-8'))))


def test_formula_prefixes_are_neutralised_in_every_export(client, db):
    from xissite.models import Customer, Purchase_info, FeedBack, LoginAttempt
    c = Customer(email='=HYPERLINK("http://x")', name='+cmd|calc')
    db.session.add(c)
    db.session.flush()
    db.session.add(Purchase_info(customer_id=c.id, city='-1+1', pay_status='paid'))
    db.session.add(FeedBack(feedbackmail='@SUM(1)', feedbacktype='General',
                            feedbackfullfield='=1+1', admin_notes='\t=x'))
    db.session.add(LoginAttempt(ip_address='1.2.3.4', user_agent='=evil()',
                                username_attempted='-admin', success=False))
    db.session.commit()

    for table in ('customers', 'purchases', 'feedback', 'logins'):
        rows = _rows(client.get(f'/api/admin/export/{table}', headers=API))
        assert len(rows) >= 2, table
        for cell in rows[1]:
            assert not cell or cell[0] not in '=+-@\t\r', f'{table}: unsafe cell {cell!r}'


def test_ordinary_values_are_untouched(client, db):
    from xissite.models import Customer
    db.session.add(Customer(email='a@b.co', name='Alice'))
    db.session.commit()
    rows = _rows(client.get('/api/admin/export/customers', headers=API))
    assert rows[1][1] == 'a@b.co'
    assert rows[1][2] == 'Alice'
