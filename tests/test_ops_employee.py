"""Employee side: see my items, act on them, never see anyone else's."""

import os

from werkzeug.security import generate_password_hash

os.environ['ADMIN_API_KEY'] = 'test-api-key-for-dual-auth'
API = {'Authorization': 'Bearer test-api-key-for-dual-auth'}


def _user(db, email, user_type='employee'):
    from xissite.models import User
    u = User(email=email, password=generate_password_hash('password1234'),
             user_type=user_type, status='active', display_name=email)
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, email):
    r = client.post('/login', data={'username': email, 'password': 'password1234'})
    assert r.status_code == 302
    # Flask-Login caches the user on g; the test fixtures keep one app context
    # open across requests, so drop the cache like a new request would.
    from flask import g
    g.pop('_login_user', None)


def _push(client, ref, **fields):
    r = client.put(f'/api/admin/ops/items/{ref}', headers=API, json=fields)
    assert r.status_code in (200, 201), r.get_json()
    return r.get_json()


def _act(client, item_id, **body):
    return client.post(f'/api/ops/items/{item_id}/events', json=body)


def test_anonymous_and_bearer_cannot_use_employee_api(client, db):
    assert client.get('/api/ops/me').status_code == 401
    assert client.get('/api/ops/me', headers=API).status_code == 401


def test_me_shows_own_and_broadcast_items_open_first(client, db):
    _user(db, 'alice')
    _user(db, 'bob')
    a = _push(client, 'a:1', kind='task', title='for alice', assignee='alice', priority='low')
    _push(client, 'b:1', kind='task', title='for bob', assignee='bob')
    bc = _push(client, 'n:1', kind='notice', title='everyone', priority='critical')
    done = _push(client, 'a:2', kind='task', title='already done', assignee='alice', status='done')
    _push(client, 'a:3', kind='task', title='gone', assignee='alice')
    client.delete('/api/admin/ops/items/a:3', headers=API)

    _login(client, 'alice')
    items = client.get('/api/ops/me').get_json()['items']
    assert [i['ref'] for i in items] == ['n:1', 'a:1', 'a:2'], 'open first, critical before low, done last'
    assert 'b:1' not in {i['ref'] for i in items}


def test_task_complete_and_reopen(client, db):
    _user(db, 'alice')
    t = _push(client, 't:1', kind='task', title='t', assignee='alice')
    _login(client, 'alice')
    d = _act(client, t['id'], action='complete', note='done at 9').get_json()
    assert d['status'] == 'done' and d['state']['done_by'] == 'alice' and d['state']['done_at']
    d = _act(client, t['id'], action='reopen').get_json()
    assert d['status'] == 'open' and d['state']['done_by'] is None
    assert _act(client, t['id'], action='tick', step_key='x').status_code == 400
    assert _act(client, t['id'], action='ack').status_code == 400
    from xissite.models import OpsEvent
    evs = OpsEvent.query.order_by(OpsEvent.id).all()
    assert [(e.action, e.note) for e in evs] == [('complete', 'done at 9'), ('reopen', None)]


def test_checklist_tick_untick_and_complete_gate(client, db):
    _user(db, 'alice')
    cl = _push(client, 'c:1', kind='checklist', title='Morning', assignee='alice',
               steps=[{'key': 'a', 'label': 'A'}, {'key': 'b', 'label': 'B'}])
    _login(client, 'alice')
    assert _act(client, cl['id'], action='complete').status_code == 400, 'steps not ticked'
    assert _act(client, cl['id'], action='tick').status_code == 400, 'step_key required'
    assert _act(client, cl['id'], action='tick', step_key='zzz').status_code == 400
    d = _act(client, cl['id'], action='tick', step_key='a').get_json()
    assert set(d['state']['steps']) == {'a'} and d['state']['steps']['a']['by'] == 'alice'
    d = _act(client, cl['id'], action='untick', step_key='a').get_json()
    assert d['state']['steps'] == {}
    _act(client, cl['id'], action='tick', step_key='a')
    _act(client, cl['id'], action='tick', step_key='b')
    d = _act(client, cl['id'], action='complete').get_json()
    assert d['status'] == 'done'


def test_notice_ack_records_per_user(client, db):
    _user(db, 'alice')
    n = _push(client, 'n:1', kind='notice', title='Heads up')
    _login(client, 'alice')
    d = _act(client, n['id'], action='ack').get_json()
    assert 'alice' in d['state']['acks'] and d['status'] == 'open'
    assert _act(client, n['id'], action='complete').status_code == 400


def test_invisible_items_are_404_and_note_is_bounded(client, db):
    _user(db, 'alice')
    _user(db, 'bob')
    b = _push(client, 'b:1', kind='task', title='bob only', assignee='bob')
    a = _push(client, 'a:1', kind='task', title='mine', assignee='alice')
    client.delete('/api/admin/ops/items/a:1', headers=API)
    _login(client, 'alice')
    assert _act(client, b['id'], action='complete').status_code == 404
    assert _act(client, a['id'], action='complete').status_code == 404, 'archived'
    assert _act(client, 99999, action='complete').status_code == 404
    mine = _push(client, 'a:2', kind='task', title='mine', assignee='alice')
    assert _act(client, mine['id'], action='complete', note='x' * 501).status_code == 400
    assert _act(client, mine['id'], action='explode').status_code == 400


def test_admin_session_can_use_employee_api(client, db):
    _user(db, 'boss', user_type='admin')
    n = _push(client, 'n:2', kind='notice', title='All hands')
    _login(client, 'boss')
    assert client.get('/api/ops/me').status_code == 200
    assert _act(client, n['id'], action='ack').status_code == 200
