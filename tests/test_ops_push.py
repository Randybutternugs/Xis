"""Admin push API: TullOps upserts items by its own ref, lists, archives."""

import os

from werkzeug.security import generate_password_hash

os.environ['ADMIN_API_KEY'] = 'test-api-key-for-dual-auth'
API = {'Authorization': 'Bearer test-api-key-for-dual-auth'}


def _user(db, email, user_type='employee', status='active'):
    from xissite.models import User
    u = User(email=email, password=generate_password_hash('password1234'),
             user_type=user_type, status=status, display_name=email)
    db.session.add(u)
    db.session.commit()
    return u


def _push(client, ref, **fields):
    return client.put(f'/api/admin/ops/items/{ref}', headers=API, json=fields)


def test_upsert_creates_then_updates(client, db):
    _user(db, 'patrick')
    r = _push(client, 'task:7', kind='task', title='Check pumps', assignee='patrick',
              priority='high', due_at='2026-09-21T13:00:00Z', body='Before 09:00')
    assert r.status_code == 201, r.get_json()
    d = r.get_json()
    assert d['ref'] == 'task:7' and d['assignee'] == 'patrick' and d['priority'] == 'high'
    assert d['due_at'] == '2026-09-21T13:00:00+00:00'

    r = _push(client, 'task:7', title='Check pumps and EC')
    assert r.status_code == 200
    d = r.get_json()
    assert d['title'] == 'Check pumps and EC'
    assert d['assignee'] == 'patrick' and d['body'] == 'Before 09:00', 'omitted fields keep their values'


def test_create_requires_kind_and_title(client, db):
    assert _push(client, 'x:1', title='no kind').status_code == 400
    assert _push(client, 'x:2', kind='task').status_code == 400
    assert _push(client, 'x:3', kind='bogus', title='t').status_code == 400


def test_validation_of_priority_steps_body_and_due(client, db):
    assert _push(client, 'v:1', kind='task', title='t', priority='urgent').status_code == 400
    assert _push(client, 'v:2', kind='checklist', title='t', steps='not a list').status_code == 400
    assert _push(client, 'v:3', kind='checklist', title='t',
                 steps=[{'key': 'a', 'label': 'A'}, {'key': 'a', 'label': 'again'}]).status_code == 400
    assert _push(client, 'v:4', kind='checklist', title='t',
                 steps=[{'key': f'k{i}', 'label': 'x'} for i in range(51)]).status_code == 400
    assert _push(client, 'v:5', kind='task', title='t', body='x' * 4001).status_code == 400
    assert _push(client, 'v:6', kind='task', title='t', due_at='tomorrow').status_code == 400
    assert _push(client, 'v:7', kind='task', title='t', status='archived').status_code == 400


def test_assignee_must_be_an_active_account(client, db):
    _user(db, 'gone', status='suspended')
    assert _push(client, 'a:1', kind='task', title='t', assignee='nobody').status_code == 404
    assert _push(client, 'a:2', kind='task', title='t', assignee='gone').status_code == 404
    r = _push(client, 'a:3', kind='task', title='t', assignee=None)
    assert r.status_code == 201 and r.get_json()['assignee'] is None
    assert _push(client, 'a:4', kind='task', title='t', assignee=['a', 'b']).status_code == 400
    assert _push(client, 'a:5', kind='task', title='t', assignee={'x': 1}).status_code == 400
    assert _push(client, 'a:6', kind='task', title='t', assignee='').status_code == 400


def test_repush_keeps_state_unless_reset(client, db):
    from xissite.models import OpsItem
    _push(client, 'cl:1', kind='checklist', title='Morning',
          steps=[{'key': 'a', 'label': 'A'}, {'key': 'b', 'label': 'B'}])
    item = OpsItem.query.filter_by(ref='cl:1').one()
    state = item.get_state()
    state['steps']['a'] = {'by': 'emp', 'at': 'x'}
    state['steps']['b'] = {'by': 'emp', 'at': 'x'}
    item.set_state(state)
    item.status = 'done'
    db.session.commit()

    # Re-push with step 'b' removed: 'a' survives, 'b' is dropped, status untouched.
    d = _push(client, 'cl:1', steps=[{'key': 'a', 'label': 'A'}]).get_json()
    assert list(d['state']['steps']) == ['a'] and d['status'] == 'done'

    d = _push(client, 'cl:1', reset_state=True).get_json()
    assert d['state']['steps'] == {} and d['status'] == 'open'


def test_list_filters_and_hides_archived_by_default(client, db):
    _user(db, 'patrick')
    _push(client, 't:1', kind='task', title='one', assignee='patrick')
    _push(client, 't:2', kind='notice', title='two')
    _push(client, 't:3', kind='task', title='three')
    assert client.delete('/api/admin/ops/items/t:3', headers=API).get_json() == {'ok': True}

    d = client.get('/api/admin/ops/items', headers=API).get_json()
    assert {i['ref'] for i in d['items']} == {'t:1', 't:2'} and d['total'] == 2
    d = client.get('/api/admin/ops/items?status=all', headers=API).get_json()
    assert d['total'] == 3
    d = client.get('/api/admin/ops/items?assignee=patrick', headers=API).get_json()
    assert [i['ref'] for i in d['items']] == ['t:1']
    d = client.get('/api/admin/ops/items?kind=notice', headers=API).get_json()
    assert [i['ref'] for i in d['items']] == ['t:2']
    assert client.get('/api/admin/ops/items?status=bogus', headers=API).status_code == 400
    assert client.get('/api/admin/ops/items?limit=abc', headers=API).status_code == 400


def test_archive_unknown_is_404_and_pushes_are_audited(client, db):
    from xissite.models import AdminAuditLog
    assert client.delete('/api/admin/ops/items/nope', headers=API).status_code == 404
    _push(client, 'z:1', kind='task', title='t')
    client.delete('/api/admin/ops/items/z:1', headers=API)
    actions = [a.action for a in AdminAuditLog.query.order_by(AdminAuditLog.id).all()]
    assert actions == ['ops.push', 'ops.archive']


def test_employee_session_cannot_use_admin_ops_api(client, db):
    _user(db, 'emp')
    client.post('/login', data={'username': 'emp', 'password': 'password1234'})
    assert client.get('/api/admin/ops/items').status_code == 401
    assert client.put('/api/admin/ops/items/x', json={'kind': 'task', 'title': 't'}).status_code == 401
