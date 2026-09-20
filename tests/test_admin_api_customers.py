import os

os.environ['ADMIN_API_KEY'] = 'test-api-key-for-dual-auth'
API = {'Authorization': 'Bearer test-api-key-for-dual-auth'}


def test_customer_list_includes_purchase_count(client, db):
    """The panel's Customers table shows purchases per customer; the list
    endpoint must carry the count so the page needs no N+1 detail calls."""
    from xissite.models import Customer, Purchase_info
    c = Customer(email='c@x.co', name='Cus')
    db.session.add(c)
    db.session.flush()
    for _ in range(2):
        db.session.add(Purchase_info(customer_id=c.id, pay_status='paid'))
    db.session.add(Customer(email='none@x.co', name='Zero'))
    db.session.commit()

    resp = client.get('/api/admin/customers', headers=API)
    assert resp.status_code == 200
    by_email = {r['email']: r for r in resp.get_json()['customers']}
    assert by_email['c@x.co']['purchase_count'] == 2
    assert by_email['none@x.co']['purchase_count'] == 0
