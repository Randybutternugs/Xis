"""OpsItem / OpsEvent round-trip their JSON columns and serialise cleanly."""

from werkzeug.security import generate_password_hash


def _employee(db, email='emp'):
    from xissite.models import User
    u = User(email=email, password=generate_password_hash('password1234'),
             user_type='employee', status='active', display_name='Emp')
    db.session.add(u)
    db.session.commit()
    return u


def test_item_defaults_and_json_accessors(db):
    from xissite.models import OpsItem
    item = OpsItem(ref='task:1', kind='task', title='Check pumps')
    db.session.add(item)
    db.session.commit()
    db.session.expire_all()
    item = OpsItem.query.filter_by(ref='task:1').one()
    assert item.priority == 'normal'
    assert item.status == 'open'
    assert item.get_steps() == []
    assert item.get_state() == {'done_by': None, 'done_at': None, 'steps': {}, 'acks': {}}
    d = item.to_dict()
    assert d['assignee'] is None
    assert d['steps'] == [] and d['state']['steps'] == {}
    assert d['pushed_at'].endswith('+00:00')


def test_item_steps_state_and_assignee_serialise(db):
    from xissite.models import OpsItem
    emp = _employee(db)
    item = OpsItem(ref='cl:1', kind='checklist', title='Morning', assignee_id=emp.id)
    item.set_steps([{'key': 'a', 'label': 'A'}, {'key': 'b', 'label': 'B'}])
    state = item.get_state()
    state['steps']['a'] = {'by': 'emp', 'at': '2026-09-20T10:00:00+00:00'}
    item.set_state(state)
    db.session.add(item)
    db.session.commit()
    db.session.expire_all()
    d = OpsItem.query.filter_by(ref='cl:1').one().to_dict()
    assert d['assignee'] == 'emp'
    assert [s['key'] for s in d['steps']] == ['a', 'b']
    assert d['state']['steps']['a']['by'] == 'emp'


def test_event_to_dict(db):
    from xissite.models import OpsItem, OpsEvent
    emp = _employee(db)
    item = OpsItem(ref='n:1', kind='notice', title='Heads up')
    db.session.add(item)
    db.session.flush()
    ev = OpsEvent(item_id=item.id, item_ref=item.ref, user_id=emp.id, username=emp.email,
                  action='ack', note='seen')
    db.session.add(ev)
    db.session.commit()
    d = ev.to_dict()
    assert d['item_ref'] == 'n:1' and d['username'] == 'emp' and d['action'] == 'ack'
    assert d['step_key'] is None and d['note'] == 'seen'
    assert d['created_at'].endswith('+00:00')
