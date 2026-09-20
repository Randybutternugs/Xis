# TullOps Content Push Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** TullOps pushes tasks, checklists and notices to named employees through the site's admin API; employees act on them at `/ops`; TullOps polls the resulting events back with a cursor.

**Architecture:** Two new tables (`ops_item`, `ops_event`) and one new Flask module `xissite/ops_api.py` holding two blueprints: `/api/admin/ops/*` (TullOps and admins, existing `require_api_key` auth) and `/api/ops/*` (employee session + CSRF header). The `/ops` page is rendered by a new `static/js/ops.js` from `/api/ops/me`; the `/admin` dashboard gains a read-mostly Ops section. Shared request-parsing helpers move to `xissite/apiutil.py`.

**Tech Stack:** Flask 3.1, Flask-SQLAlchemy 3.1 / SQLAlchemy 2.0, Flask-Login, Flask-WTF CSRF, pytest. Plain JS, no build step.

**Spec:** `docs/superpowers/specs/2026-09-20-ops-content-push-design.md`

## Global Constraints

- Python 3.12 on App Engine, 3.14 locally; no new third-party dependencies.
- All datetimes are written aware UTC and read back naive from SQLite; every comparison goes through `xissite/timeutil.as_utc()`.
- Every value rendered into HTML by JS goes through the quote-safe `esc()` pattern already used in `admin_dashboard.js` (escapes `& < > " '`).
- Every JS mutation checks the response (`checked()` pattern) and reports the server's `error` in a toast; never a success toast on a 4xx/5xx.
- Numeric query/body parameters are parsed with the bounded integer helper; bad values are JSON 400, never 500.
- Limits from the spec: title ≤ 200, body ≤ 4000, note ≤ 500, steps ≤ 50 with unique keys, events per poll ≤ 500.
- Kinds: `task`, `checklist`, `notice`. Priorities: `low`, `normal`, `high`, `critical`. Statuses: `open`, `done`, `archived`. Actions: `complete`, `reopen`, `tick`, `untick`, `ack`.
- Employees never learn about items they cannot see: invisible or archived is 404.
- Tests run with: `.venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider` (Windows) — the site suite must stay green (118 passing at plan time). Panel suite: `.venv-admin\Scripts\python.exe -m pytest admin_panel/tests/ -q`.
- Commit after every task with a `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` trailer. Work on branch `feat/ops-content-push` off `main`.
- Test files set `os.environ['ADMIN_API_KEY'] = 'test-api-key-for-dual-auth'` at import (the shared `conftest.py` does not), and use `API = {'Authorization': 'Bearer test-api-key-for-dual-auth'}`.
- The shared fixtures (`tests/conftest.py`) give `app` (session-scoped, in-memory SQLite, CSRF disabled), `db` (fresh tables per test) and `client`. `create_app()` creates the bootstrap admin `admin` / `testpassword123` at session start; the per-test `db` fixture drops it, so tests seed their own users.

---

## File Structure

| File | Responsibility |
|---|---|
| `xissite/models.py` (modify) | Add `OpsItem` and `OpsEvent` models with JSON accessors and `to_dict()` |
| `xissite/apiutil.py` (create) | `int_arg()` bounded integer parser and `json_errors(bp)` that registers JSON 400/404 handlers on a blueprint. Extracted from `admin_api.py` so both API modules share it |
| `xissite/admin_api.py` (modify) | Import `int_arg` from `apiutil` instead of defining it; keep the `_int_arg` alias (the panel contract test parses that name) |
| `xissite/ops_api.py` (create) | `ops_admin` blueprint (`/api/admin/ops`): upsert, list, archive, events. `ops_me` blueprint (`/api/ops`): my items, record event. `apply_action()` holds the per-kind rules |
| `xissite/__init__.py` (modify) | Register the two blueprints |
| `xissite/templates/employee_ops.html` (modify) | Drop placeholder content; three empty section shells, CSRF meta, `data-username`, loads `ops.js` |
| `xissite/static/js/ops.js` (create) | Fetches `/api/ops/me`, renders tasks / checklists / notices, posts actions |
| `xissite/templates/admin_dashboard.html` (modify) | Nav link and `sec-ops` section card |
| `xissite/static/js/admin_dashboard.js` (modify) | `fetchOps()`, `renderOps()`, `archiveOps()`; `fetchOps` added to `refresh()` |
| `tests/test_ops_models.py` (create) | Model round-trips |
| `tests/test_ops_push.py` (create) | Admin API: upsert, list, archive, events |
| `tests/test_ops_employee.py` (create) | Employee API and action rules |
| `tests/test_ops_pages.py` (create) | `/ops` and `/admin` render the new pieces |
| `tests/test_panel_contract.py` (modify) | Add `ops.js` and the dashboard's Ops code to the field-name contract |
| `docs/ops-content-push.md` (create) | The contract TullOps codes against |

---

### Task 1: Models

**Files:**
- Modify: `xissite/models.py` (append after `Purchase_info`)
- Test: `tests/test_ops_models.py`

**Interfaces:**
- Produces: `OpsItem` with class constants `KINDS`, `PRIORITIES`, `STATUSES`, `EMPTY_STATE`; methods `get_steps() -> list`, `set_steps(list|None)`, `get_state() -> dict`, `set_state(dict|None)`, `to_dict() -> dict`; relationship `assignee` (User or None). `OpsEvent` with `ACTIONS` and `to_dict()`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ops_models.py
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ops_models.py -q -p no:cacheprovider`
Expected: 3 failed with `ImportError: cannot import name 'OpsItem'`.

- [ ] **Step 3: Add the models**

Append to `xissite/models.py` (after the `Purchase_info` class). Add `import json` to the imports at the top of the file and `from .timeutil import as_utc` there too.

```python
# ============================================================================
# OPS CONTENT (pushed by TullOps, acted on by employees)
# ============================================================================
class OpsItem(db.Model):
    """One task, checklist or notice pushed by TullOps.

    `ref` is TullOps's own identifier and the upsert key. `assignee_id` null
    means everyone sees it. `steps` and `state` are JSON text columns; use
    the get_/set_ accessors. `state` is derived from OpsEvent rows and kept
    here so pages can render without replaying events.
    """
    __tablename__ = 'ops_item'

    KINDS = ('task', 'checklist', 'notice')
    PRIORITIES = ('low', 'normal', 'high', 'critical')
    STATUSES = ('open', 'done', 'archived')

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(200), unique=True, nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=True)
    steps = db.Column(db.Text, nullable=True)
    assignee_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    priority = db.Column(db.String(10), default='normal')
    due_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(10), default='open', index=True)
    state = db.Column(db.Text, nullable=True)
    pushed_at = db.Column(db.DateTime(timezone=True), default=func.now())
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), default=func.now(), onupdate=func.now())

    assignee = db.relationship('User', foreign_keys=[assignee_id])

    @staticmethod
    def empty_state():
        return {'done_by': None, 'done_at': None, 'steps': {}, 'acks': {}}

    def get_steps(self):
        return json.loads(self.steps) if self.steps else []

    def set_steps(self, steps):
        self.steps = json.dumps(steps) if steps else None

    def get_state(self):
        state = self.empty_state()
        if self.state:
            state.update(json.loads(self.state))
        return state

    def set_state(self, state):
        self.state = json.dumps(state if state is not None else self.empty_state())

    @staticmethod
    def _iso(dt):
        return as_utc(dt).isoformat() if dt else None

    def to_dict(self):
        return {
            'id': self.id,
            'ref': self.ref,
            'kind': self.kind,
            'title': self.title,
            'body': self.body,
            'steps': self.get_steps(),
            'assignee': self.assignee.email if self.assignee else None,
            'priority': self.priority,
            'due_at': self._iso(self.due_at),
            'status': self.status,
            'state': self.get_state(),
            'pushed_at': self._iso(self.pushed_at),
            'created_at': self._iso(self.created_at),
            'updated_at': self._iso(self.updated_at),
        }

    def __repr__(self):
        return f'<OpsItem {self.ref} {self.kind} {self.status}>'


class OpsEvent(db.Model):
    """Append-only record of what an employee did to an OpsItem.

    The auto-increment id is the cursor TullOps polls with. item_ref and
    username are copied in so the feed needs no joins and survives archives.
    """
    __tablename__ = 'ops_event'

    ACTIONS = ('complete', 'reopen', 'tick', 'untick', 'ack')

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('ops_item.id'), nullable=False, index=True)
    item_ref = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    username = db.Column(db.String(150), nullable=False)
    action = db.Column(db.String(20), nullable=False)
    step_key = db.Column(db.String(100), nullable=True)
    note = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'item_id': self.item_id,
            'item_ref': self.item_ref,
            'username': self.username,
            'action': self.action,
            'step_key': self.step_key,
            'note': self.note,
            'created_at': as_utc(self.created_at).isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<OpsEvent {self.id} {self.item_ref} {self.action} by {self.username}>'
```

Also add the two names to the model import in `create_app()` in `xissite/__init__.py` (the line `from .models import (Customer, Purchase_info, User, FeedBack, ...)`), so `db.create_all()` sees them: append `OpsItem, OpsEvent`.

- [ ] **Step 4: Run to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ops_models.py -q -p no:cacheprovider`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git checkout -b feat/ops-content-push
git add xissite/models.py xissite/__init__.py tests/test_ops_models.py
git commit -m "feat(ops): OpsItem and OpsEvent models

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Shared API helpers

**Files:**
- Create: `xissite/apiutil.py`
- Modify: `xissite/admin_api.py` (replace the `_int_arg` definition and the `_bad_request` handler; keep the names)
- Test: `tests/test_apiutil.py`

**Interfaces:**
- Produces: `int_arg(name, default, lo=None, hi=None, source=None) -> int` (raises `werkzeug.exceptions.BadRequest`), `json_errors(bp)` which registers JSON handlers for 400 and 404 on a blueprint and returns it.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_apiutil.py
import pytest
from werkzeug.exceptions import BadRequest


def test_int_arg_parses_clamps_and_rejects(app):
    from xissite.apiutil import int_arg
    with app.test_request_context('/?n=7&big=9999&bad=x'):
        assert int_arg('n', 1) == 7
        assert int_arg('missing', 3) == 3
        assert int_arg('big', 1, 1, 100) == 100
        assert int_arg('n', 1, 10) == 10
        with pytest.raises(BadRequest):
            int_arg('bad', 1)


def test_int_arg_reads_a_body_dict():
    from xissite.apiutil import int_arg
    assert int_arg('hours', 0, 1, 24, source={'hours': '12'}) == 12
    with pytest.raises(BadRequest):
        int_arg('hours', 0, source={'hours': 'soon'})


def test_json_errors_turns_400_and_404_into_json(app):
    from flask import Blueprint, Flask, abort
    from xissite.apiutil import json_errors
    bp = json_errors(Blueprint('t', __name__, url_prefix='/t'))

    @bp.route('/bad')
    def bad():
        raise BadRequest('nope')

    @bp.route('/missing')
    def missing():
        abort(404, description='no such thing')

    test_app = Flask('t')
    test_app.register_blueprint(bp)
    c = test_app.test_client()
    assert c.get('/t/bad').get_json() == {'error': 'nope'}
    assert c.get('/t/bad').status_code == 400
    assert c.get('/t/missing').get_json() == {'error': 'no such thing'}
    assert c.get('/t/missing').status_code == 404
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_apiutil.py -q -p no:cacheprovider`
Expected: 3 failed, `ModuleNotFoundError: No module named 'xissite.apiutil'`.

- [ ] **Step 3: Create the module and point admin_api at it**

```python
# xissite/apiutil.py
"""Request-parsing helpers shared by the JSON API blueprints."""

from flask import jsonify, request
from werkzeug.exceptions import BadRequest, NotFound


def int_arg(name, default, lo=None, hi=None, source=None):
    """Integer query/body parameter with bounds. Non-numeric -> 400, never 500.

    `source` defaults to request.args; pass a dict to read a JSON body.
    """
    raw = (source if source is not None else request.args).get(name, default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise BadRequest(f'{name} must be an integer')
    if lo is not None and value < lo:
        value = lo
    if hi is not None and value > hi:
        value = hi
    return value


def json_errors(bp):
    """Register JSON bodies for 400 and 404 raised inside `bp`."""
    @bp.errorhandler(BadRequest)
    def _bad_request(e):
        return jsonify(error=e.description or 'Bad request'), 400

    @bp.errorhandler(NotFound)
    def _not_found(e):
        return jsonify(error=e.description or 'Not found'), 404

    return bp
```

In `xissite/admin_api.py`:

1. Replace the block from `@admin_api.errorhandler(BadRequest)` through the end of the `_int_arg` function (the two definitions under `# REQUEST PARSING HELPERS`) with:

```python
from .apiutil import int_arg as _int_arg, json_errors

json_errors(admin_api)
```

   Keep the `_SafeCsvWriter` class that follows; keep `from werkzeug.exceptions import BadRequest` because the ban handler still raises it.
2. Nothing else changes: every call site already uses `_int_arg(...)` and the panel contract test parses that exact name.

- [ ] **Step 4: Run to verify it passes, and that nothing regressed**

Run: `.venv\Scripts\python.exe -m pytest tests/test_apiutil.py tests/test_api_input_validation.py tests/test_panel_contract.py -q -p no:cacheprovider`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add xissite/apiutil.py xissite/admin_api.py tests/test_apiutil.py
git commit -m "refactor(api): share int_arg and JSON error handlers via apiutil

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Admin push API — upsert, list, archive

**Files:**
- Create: `xissite/ops_api.py`
- Modify: `xissite/__init__.py:196-201` (blueprint registration)
- Test: `tests/test_ops_push.py`

**Interfaces:**
- Consumes: `OpsItem`, `OpsEvent`, `User` (Task 1); `int_arg`, `json_errors` (Task 2); `require_api_key`, `_audit` from `xissite/admin_api.py`; `as_utc`, `utcnow` from `xissite/timeutil.py`.
- Produces: blueprint `ops_admin` (`/api/admin/ops`) with `PUT /items/<ref>`, `GET /items`, `DELETE /items/<ref>`; module constants `MAX_TITLE=200`, `MAX_BODY=4000`, `MAX_NOTE=500`, `MAX_STEPS=50`; helpers `_validate_steps(steps) -> list`, `_parse_due(value) -> naive UTC datetime|None`. Blueprint `ops_me` is declared here too (empty until Task 5).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ops_push.py
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ops_push.py -q -p no:cacheprovider`
Expected: every test fails with 404s (no routes) or assertion errors; no import errors once Task 1 is in.

- [ ] **Step 3: Create `xissite/ops_api.py`**

```python
# xissite/ops_api.py
"""
Ops content: TullOps pushes tasks, checklists and notices; employees act
on them; TullOps polls the actions back.

Two blueprints:
  ops_admin  /api/admin/ops   Bearer key or admin session (require_api_key)
  ops_me     /api/ops         employee/admin browser session + CSRF header

Design: docs/superpowers/specs/2026-09-20-ops-content-push-design.md
"""

import functools
from datetime import datetime

from flask import Blueprint, request, jsonify, abort
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from sqlalchemy import desc, func
from werkzeug.exceptions import BadRequest

from . import db
from .admin_api import require_api_key, _audit
from .apiutil import int_arg, json_errors
from .models import OpsItem, OpsEvent, User
from .timeutil import as_utc, utcnow

ops_admin = json_errors(Blueprint('ops_admin', __name__, url_prefix='/api/admin/ops'))
ops_me = json_errors(Blueprint('ops_me', __name__, url_prefix='/api/ops'))

MAX_TITLE = 200
MAX_BODY = 4000
MAX_NOTE = 500
MAX_STEPS = 50
MAX_EVENTS = 500


# ============================================================================
# VALIDATION HELPERS
# ============================================================================

def _validate_steps(steps):
    """Return a clean list of {key, label}; raise BadRequest otherwise."""
    if steps is None:
        return []
    if not isinstance(steps, list) or len(steps) > MAX_STEPS:
        raise BadRequest(f'steps must be a list of at most {MAX_STEPS} entries')
    out, keys = [], set()
    for step in steps:
        if not isinstance(step, dict) or not step.get('key') or not step.get('label'):
            raise BadRequest('each step needs a key and a label')
        key = str(step['key'])[:100]
        if key in keys:
            raise BadRequest(f'duplicate step key: {key}')
        keys.add(key)
        out.append({'key': key, 'label': str(step['label'])[:200]})
    return out


def _parse_due(value):
    """ISO 8601 in; naive UTC datetime out (how SQLite stores it); None for blank."""
    if value in (None, ''):
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        raise BadRequest('due_at must be an ISO 8601 datetime')
    return as_utc(dt).replace(tzinfo=None)


def _resolve_assignee(username):
    """User for a username, or 404. None stays None (broadcast)."""
    if username is None:
        return None
    user = User.query.filter_by(email=username).first()
    if user is None or user.status != 'active':
        abort(404, description='assignee not found or not active')
    return user


# ============================================================================
# ADMIN: PUSH / LIST / ARCHIVE
# ============================================================================

@ops_admin.route('/items/<path:ref>', methods=['PUT'])
@require_api_key
def upsert_item(ref):
    data = request.get_json(silent=True) or {}
    item = OpsItem.query.filter_by(ref=ref).first()
    created = item is None

    if created:
        if data.get('kind') not in OpsItem.KINDS:
            raise BadRequest('kind must be one of task, checklist, notice')
        if not str(data.get('title') or '').strip():
            raise BadRequest('title is required')
        item = OpsItem(ref=ref, kind=data['kind'], title='')
        item.set_state(None)
        db.session.add(item)

    if 'kind' in data:
        if data['kind'] not in OpsItem.KINDS:
            raise BadRequest('kind must be one of task, checklist, notice')
        item.kind = data['kind']
    if 'title' in data:
        title = str(data['title'] or '').strip()
        if not title or len(title) > MAX_TITLE:
            raise BadRequest(f'title is required and at most {MAX_TITLE} characters')
        item.title = title
    if 'body' in data:
        body = data['body']
        if body is not None and len(str(body)) > MAX_BODY:
            raise BadRequest(f'body must be at most {MAX_BODY} characters')
        item.body = None if body is None else str(body)
    if 'steps' in data:
        steps = _validate_steps(data['steps'])
        item.set_steps(steps)
        state = item.get_state()
        keep = {s['key'] for s in steps}
        state['steps'] = {k: v for k, v in state['steps'].items() if k in keep}
        item.set_state(state)
    if 'assignee' in data:
        user = _resolve_assignee(data['assignee'])
        item.assignee_id = user.id if user else None
    if 'priority' in data:
        if data['priority'] not in OpsItem.PRIORITIES:
            raise BadRequest('priority must be one of low, normal, high, critical')
        item.priority = data['priority']
    if 'due_at' in data:
        item.due_at = _parse_due(data['due_at'])
    if 'status' in data:
        if data['status'] not in ('open', 'done'):
            raise BadRequest('status must be open or done; archive with DELETE')
        item.status = data['status']
    if data.get('reset_state'):
        item.set_state(None)
        item.status = 'open'

    item.pushed_at = utcnow()
    db.session.commit()
    _audit('ops.push', 'ops_item', item.id,
           {'ref': ref, 'kind': item.kind, 'assignee': item.assignee.email if item.assignee else None})
    return jsonify(item.to_dict()), (201 if created else 200)


@ops_admin.route('/items')
@require_api_key
def list_items():
    q = OpsItem.query
    status = request.args.get('status')
    if status == 'all':
        pass
    elif status:
        if status not in OpsItem.STATUSES:
            raise BadRequest('status must be open, done, archived or all')
        q = q.filter_by(status=status)
    else:
        q = q.filter(OpsItem.status != 'archived')
    kind = request.args.get('kind')
    if kind:
        if kind not in OpsItem.KINDS:
            raise BadRequest('kind must be one of task, checklist, notice')
        q = q.filter_by(kind=kind)
    assignee = request.args.get('assignee')
    if assignee:
        user = User.query.filter_by(email=assignee).first()
        if user is None:
            return jsonify(items=[], total=0)
        q = q.filter_by(assignee_id=user.id)
    limit = int_arg('limit', 200, 1, 500)
    total = q.count()
    items = q.order_by(desc(OpsItem.pushed_at), desc(OpsItem.id)).limit(limit).all()
    return jsonify(items=[i.to_dict() for i in items], total=total)


@ops_admin.route('/items/<path:ref>', methods=['DELETE'])
@require_api_key
def archive_item(ref):
    item = OpsItem.query.filter_by(ref=ref).first()
    if item is None:
        abort(404, description='no item with that ref')
    item.status = 'archived'
    db.session.commit()
    _audit('ops.archive', 'ops_item', item.id, {'ref': ref})
    return jsonify(ok=True)
```

Register both blueprints in `xissite/__init__.py`, next to the existing registrations:

```python
    from .admin_api import admin_api
    from .ops_api import ops_admin, ops_me

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(sales, url_prefix='/')
    app.register_blueprint(admin_api)
    app.register_blueprint(ops_admin)
    app.register_blueprint(ops_me)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ops_push.py -q -p no:cacheprovider`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add xissite/ops_api.py xissite/__init__.py tests/test_ops_push.py
git commit -m "feat(ops): admin push API - upsert by ref, list, archive

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Events feed with cursor and reset signal

**Files:**
- Modify: `xissite/ops_api.py` (append)
- Test: `tests/test_ops_push.py` (append)

**Interfaces:**
- Consumes: `OpsEvent`, `int_arg`, `MAX_EVENTS`.
- Produces: `GET /api/admin/ops/events?after=&limit=` returning `{events, next_after, reset}`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_ops_push.py`)

```python
def _event(db, item, user, action, n=1):
    from xissite.models import OpsEvent
    for _ in range(n):
        db.session.add(OpsEvent(item_id=item.id, item_ref=item.ref, user_id=user.id,
                                username=user.email, action=action))
    db.session.commit()


def test_events_feed_orders_by_id_and_advances_cursor(client, db):
    from xissite.models import OpsItem
    emp = _user(db, 'emp')
    _push(client, 'e:1', kind='task', title='t')
    item = OpsItem.query.filter_by(ref='e:1').one()
    _event(db, item, emp, 'complete')
    _event(db, item, emp, 'reopen')
    _event(db, item, emp, 'complete')

    d = client.get('/api/admin/ops/events', headers=API).get_json()
    assert [e['action'] for e in d['events']] == ['complete', 'reopen', 'complete']
    assert d['reset'] is False and d['next_after'] == d['events'][-1]['id']

    d2 = client.get(f"/api/admin/ops/events?after={d['next_after']}", headers=API).get_json()
    assert d2['events'] == [] and d2['next_after'] == d['next_after'] and d2['reset'] is False

    d3 = client.get('/api/admin/ops/events?after=1&limit=1', headers=API).get_json()
    assert len(d3['events']) == 1 and d3['events'][0]['id'] == 2 and d3['next_after'] == 2


def test_events_feed_signals_reset_when_cursor_is_ahead_of_data(client, db):
    from xissite.models import OpsItem
    emp = _user(db, 'emp')
    _push(client, 'e:2', kind='notice', title='t')
    item = OpsItem.query.filter_by(ref='e:2').one()
    _event(db, item, emp, 'ack')
    # TullOps remembers cursor 999 from before the database was wiped.
    d = client.get('/api/admin/ops/events?after=999', headers=API).get_json()
    assert d['reset'] is True
    assert [e['action'] for e in d['events']] == ['ack']
    assert d['next_after'] == d['events'][-1]['id']


def test_events_feed_with_no_events_and_stale_cursor(client, db):
    d = client.get('/api/admin/ops/events?after=5', headers=API).get_json()
    assert d == {'events': [], 'next_after': 0, 'reset': True}
    assert client.get('/api/admin/ops/events?after=x', headers=API).status_code == 400
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ops_push.py -q -p no:cacheprovider -k events`
Expected: 3 failed with 404.

- [ ] **Step 3: Append the endpoint to `xissite/ops_api.py`**

```python
# ============================================================================
# ADMIN: EVENTS FEED (TullOps polls this)
# ============================================================================

@ops_admin.route('/events')
@require_api_key
def list_events():
    """Events with id > after, ascending. If `after` is beyond the newest id
    the database has been reset since the caller last polled: start over and
    say so, so the caller re-pushes its open items."""
    after = int_arg('after', 0, 0)
    limit = int_arg('limit', 200, 1, MAX_EVENTS)
    newest = db.session.query(func.max(OpsEvent.id)).scalar() or 0
    reset = after > newest
    if reset:
        after = 0
    events = (OpsEvent.query.filter(OpsEvent.id > after)
              .order_by(OpsEvent.id).limit(limit).all())
    next_after = events[-1].id if events else after
    return jsonify(events=[e.to_dict() for e in events], next_after=next_after, reset=reset)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ops_push.py -q -p no:cacheprovider`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add xissite/ops_api.py tests/test_ops_push.py
git commit -m "feat(ops): events feed with cursor and reset signal

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Employee API — my items and actions

**Files:**
- Modify: `xissite/ops_api.py` (append)
- Test: `tests/test_ops_employee.py`

**Interfaces:**
- Consumes: `ops_me` blueprint, `OpsItem`, `OpsEvent`, `utcnow`, `MAX_NOTE`.
- Produces: `require_employee_session(f)` decorator; `apply_action(item, user, action, step_key=None, note=None) -> OpsEvent` (raises `BadRequest`, does not commit); `GET /api/ops/me` → `{items}`; `POST /api/ops/items/<int:item_id>/events` → item dict.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ops_employee.py
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ops_employee.py -q -p no:cacheprovider`
Expected: 7 failed (404s for missing routes; the first test fails because an unregistered path is 404 not 401).

- [ ] **Step 3: Append to `xissite/ops_api.py`**

```python
# ============================================================================
# EMPLOYEE: MY ITEMS AND ACTIONS
# ============================================================================

def require_employee_session(f):
    """Browser session with employee or admin role; CSRF header on mutations.
    No Bearer access: these endpoints act as a person."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or \
                getattr(current_user, 'user_type', None) not in ('employee', 'admin'):
            return jsonify(error='Unauthorized'), 401
        if request.method != 'GET':
            try:
                validate_csrf(request.headers.get('X-CSRFToken', ''))
            except Exception:
                return jsonify(error='CSRF validation failed'), 403
        return f(*args, **kwargs)
    return decorated


ALLOWED_ACTIONS = {
    'task': ('complete', 'reopen'),
    'checklist': ('tick', 'untick', 'complete', 'reopen'),
    'notice': ('ack',),
}
PRIORITY_RANK = {'critical': 0, 'high': 1, 'normal': 2, 'low': 3}


def _visible_to(user):
    return OpsItem.query.filter(OpsItem.status != 'archived').filter(
        (OpsItem.assignee_id == user.id) | (OpsItem.assignee_id == None)  # noqa: E711
    )


def apply_action(item, user, action, step_key=None, note=None):
    """Validate `action` against the item's kind, update item.state/status
    and add an OpsEvent to the session. Raises BadRequest. Caller commits."""
    if action not in ALLOWED_ACTIONS[item.kind]:
        raise BadRequest(f'{action} is not allowed on a {item.kind}')
    if note is not None:
        note = str(note)
        if len(note) > MAX_NOTE:
            raise BadRequest(f'note must be at most {MAX_NOTE} characters')
    state = item.get_state()
    now = utcnow().isoformat()

    if action in ('tick', 'untick'):
        keys = {s['key'] for s in item.get_steps()}
        if not step_key or step_key not in keys:
            raise BadRequest('step_key must name one of the checklist steps')
        if action == 'tick':
            state['steps'][step_key] = {'by': user.email, 'at': now}
        else:
            state['steps'].pop(step_key, None)
    elif action == 'complete':
        if item.kind == 'checklist':
            missing = [s['key'] for s in item.get_steps() if s['key'] not in state['steps']]
            if missing:
                raise BadRequest('all steps must be ticked before completing')
        item.status = 'done'
        state['done_by'] = user.email
        state['done_at'] = now
    elif action == 'reopen':
        item.status = 'open'
        state['done_by'] = None
        state['done_at'] = None
    elif action == 'ack':
        state['acks'][user.email] = now

    item.set_state(state)
    event = OpsEvent(item_id=item.id, item_ref=item.ref, user_id=user.id,
                     username=user.email, action=action,
                     step_key=step_key if action in ('tick', 'untick') else None,
                     note=note)
    db.session.add(event)
    return event


@ops_me.route('/me')
@require_employee_session
def my_items():
    items = _visible_to(current_user).all()
    items.sort(key=lambda i: (
        i.status != 'open',
        PRIORITY_RANK.get(i.priority, 2),
        i.due_at is None,
        i.due_at or datetime.max,
        -i.id,
    ))
    return jsonify(items=[i.to_dict() for i in items])


@ops_me.route('/items/<int:item_id>/events', methods=['POST'])
@require_employee_session
def record_event(item_id):
    item = _visible_to(current_user).filter(OpsItem.id == item_id).first()
    if item is None:
        abort(404, description='Not found')
    data = request.get_json(silent=True) or {}
    action = data.get('action')
    if action not in OpsEvent.ACTIONS:
        raise BadRequest('action must be one of complete, reopen, tick, untick, ack')
    apply_action(item, current_user, action, data.get('step_key'), data.get('note'))
    db.session.commit()
    return jsonify(item.to_dict())
```

- [ ] **Step 4: Run to verify it passes, plus the full suite**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ops_employee.py -q -p no:cacheprovider`
Expected: 7 passed.
Run: `.venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider`
Expected: all passed (118 + new).

- [ ] **Step 5: Commit**

```bash
git add xissite/ops_api.py tests/test_ops_employee.py
git commit -m "feat(ops): employee API - my items and per-kind actions

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: The `/ops` page

**Files:**
- Modify: `xissite/templates/employee_ops.html` (replace everything from `<!-- My Tasks -->` to the closing `</div>` of `.ops-content`, remove the inline `<script>` at the bottom; add the CSRF meta and `data-username`)
- Create: `xissite/static/js/ops.js`
- Test: `tests/test_ops_pages.py`

**Interfaces:**
- Consumes: `GET /api/ops/me` item shape (`id, ref, kind, title, body, steps[], assignee, priority, due_at, status, state{done_by, done_at, steps{key:{by,at}}, acks{username:at}}`), `POST /api/ops/items/<id>/events`.
- Produces: page elements `#ops-tasks`, `#ops-checklists`, `#ops-notices`, `#ops-toast`; global `window.opsAct(id, action, stepKey)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ops_pages.py
"""/ops and /admin carry the ops UI and none of the old placeholder copy."""

from werkzeug.security import generate_password_hash


def _login_as(client, db, email, user_type):
    from xissite.models import User
    db.session.add(User(email=email, password=generate_password_hash('password1234'),
                        user_type=user_type, status='active', display_name=email))
    db.session.commit()
    assert client.post('/login', data={'username': email, 'password': 'password1234'}).status_code == 302
    from flask import g
    g.pop('_login_user', None)


def test_ops_page_is_driven_by_the_api(client, db):
    _login_as(client, db, 'emp', 'employee')
    html = client.get('/ops').data.decode()
    assert 'js/ops.js' in html
    assert 'name="csrf-token"' in html
    assert 'data-username="emp"' in html
    for anchor in ('id="ops-tasks"', 'id="ops-checklists"', 'id="ops-notices"', 'id="ops-toast"'):
        assert anchor in html
    for placeholder in ('Tower 7', 'Morning Startup Checklist', 'End of Day Shutdown', 'Reservoir B'):
        assert placeholder not in html
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ops_pages.py -q -p no:cacheprovider`
Expected: 1 failed (`js/ops.js` not in page).

- [ ] **Step 3: Rewrite the page body and add `ops.js`**

In `xissite/templates/employee_ops.html`:

1. In `<head>`, after the viewport meta, add `<meta name="csrf-token" content="{{ csrf_token() }}">`.
2. Change `<body>` to `<body data-username="{{ user.email }}">`.
3. Replace everything from the line `<!-- My Tasks -->` through the end of the `<div class="ops-content">` block, and delete the inline `<script>...</script>` before `</body>`, so the file ends:

```html
    <!-- My Tasks -->
    <div class="ops-section">
        <h2>// My Tasks</h2>
        <div id="ops-tasks"><div class="ops-empty">Loading...</div></div>
    </div>

    <!-- My Checklists -->
    <div class="ops-section">
        <h2>// My Checklists</h2>
        <div id="ops-checklists"><div class="ops-empty">Loading...</div></div>
    </div>

    <!-- Notices -->
    <div class="ops-section">
        <h2>// Notices</h2>
        <div id="ops-notices"><div class="ops-empty">Loading...</div></div>
    </div>

</div>

<div class="toast" id="ops-toast"></div>

<style>
.ops-empty{padding:18px;color:var(--mut,#666);font-family:Consolas,monospace;font-size:.85em}
.ops-actions{display:flex;gap:6px;margin-top:8px;flex-wrap:wrap}
.ops-task.done .ops-task-title{text-decoration:line-through;opacity:.6}
.ops-notif.acked{opacity:.55}
.ops-checklist-item input{margin-right:8px}
.toast{position:fixed;bottom:20px;right:20px;background:#1a3a1a;color:var(--g,#6ABD45);border:1px solid var(--g,#6ABD45);padding:10px 16px;font-size:.85em;opacity:0;transition:opacity .2s;pointer-events:none;z-index:50}
.toast.show{opacity:1}
.toast.err{background:#1a0a0a;color:var(--crit,#f33);border-color:var(--crit,#f33)}
</style>
<script src="{{ url_for('static', filename='js/ops.js') }}"></script>

</body>
</html>
```

Create `xissite/static/js/ops.js`:

```javascript
// Employee operations page: renders /api/ops/me and posts actions.
// Field names follow OpsItem.to_dict() in xissite/models.py; the contract
// test in tests/test_panel_contract.py fails if this drifts from the API.
(function(){
  var API='/api/ops';
  var CSRF=document.querySelector('meta[name="csrf-token"]')?.content||'';
  var ME=document.body.getAttribute('data-username')||'';
  var els={tasks:document.getElementById('ops-tasks'),checklists:document.getElementById('ops-checklists'),
           notices:document.getElementById('ops-notices'),toast:document.getElementById('ops-toast')};

  function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;')}
  function checked(r){return r.json().catch(function(){return {}}).then(function(d){if(!r.ok)throw new Error(d.error||('HTTP '+r.status));return d})}
  function toast(msg,isError){els.toast.textContent=msg;els.toast.className='toast show'+(isError?' err':'');setTimeout(function(){els.toast.className='toast'},3000)}
  function when(iso){if(!iso)return '';var d=new Date(iso);return d.toLocaleString()}
  function due(iso){
    if(!iso)return '';
    var ms=new Date(iso).getTime()-Date.now(),h=Math.round(Math.abs(ms)/36e5);
    var span=h<1?'under an hour':h<48?h+'h':Math.round(h/24)+'d';
    return ms<0?'<span class="crit">overdue '+span+'</span>':'due in '+span;
  }
  function prio(p){var c=p==='critical'?'crit':p==='high'?'warn':'ok';return '<span class="'+c+'">'+esc(p)+'</span>'}
  function dot(item){return item.status==='done'?'dot-g':item.priority==='critical'?'dot-r':item.priority==='high'?'dot-y':'dot-g'}

  function renderTasks(items){
    if(!items.length){els.tasks.innerHTML='<div class="ops-empty">Nothing assigned to you yet.</div>';return}
    var html='';
    items.forEach(function(item){
      var done=item.status==='done';
      html+='<div class="ops-task'+(done?' done':'')+'"><div class="ops-task-status"><span class="dot '+dot(item)+'"></span></div><div class="ops-task-body">'+
        '<div class="ops-task-title">'+esc(item.title)+'</div>'+
        (item.body?'<div class="ops-task-desc">'+esc(item.body)+'</div>':'')+
        '<div class="ops-task-meta">'+(done?'<span class="badge-ok">Completed by '+esc(item.state.done_by||'')+' '+esc(when(item.state.done_at))+'</span>':'<span>Open</span>')+
        (item.due_at?'<span title="'+esc(when(item.due_at))+'">'+due(item.due_at)+'</span>':'')+'<span>Priority: '+prio(item.priority)+'</span></div>'+
        '<div class="ops-actions">'+(done?'<button class="btn btn-sm btn-outline" onclick="opsAct('+item.id+',\'reopen\')">Reopen</button>':
          '<button class="btn btn-sm btn-primary" onclick="opsAct('+item.id+',\'complete\')">Mark done</button>')+'</div></div></div>';
    });
    els.tasks.innerHTML=html;
  }

  function renderChecklists(items){
    if(!items.length){els.checklists.innerHTML='<div class="ops-empty">No checklists assigned.</div>';return}
    var html='';
    items.forEach(function(item){
      var ticked=item.state.steps||{},total=item.steps.length,doneN=item.steps.filter(function(s){return ticked[s.key]}).length;
      var allDone=total>0&&doneN===total,done=item.status==='done';
      html+='<div class="ops-checklist"><div class="ops-checklist-title">'+esc(item.title)+(done?' <span class="badge-ok">Done</span>':'')+'</div>'+
        (item.body?'<div class="ops-task-desc">'+esc(item.body)+'</div>':'');
      item.steps.forEach(function(step){
        var on=!!ticked[step.key],by=on?' title="'+esc(ticked[step.key].by)+' '+esc(when(ticked[step.key].at))+'"':'';
        html+='<label class="ops-checklist-item'+(on?' checked':'')+'"'+by+'><input type="checkbox"'+(on?' checked':'')+(done?' disabled':'')+
          ' onchange="opsAct('+item.id+',this.checked?\'tick\':\'untick\',\''+esc(step.key)+'\')">'+esc(step.label)+'</label>';
      });
      html+='<div class="ops-checklist-progress">'+doneN+' / '+total+' complete'+(item.due_at?' &middot; '+due(item.due_at):'')+'</div>'+
        '<div class="ops-actions">'+(done?'<button class="btn btn-sm btn-outline" onclick="opsAct('+item.id+',\'reopen\')">Reopen</button>':
          (allDone?'<button class="btn btn-sm btn-primary" onclick="opsAct('+item.id+',\'complete\')">Mark done</button>':''))+'</div></div>';
    });
    els.checklists.innerHTML=html;
  }

  function renderNotices(items){
    if(!items.length){els.notices.innerHTML='<div class="ops-empty">No notices.</div>';return}
    var html='';
    items.slice().sort(function(a,b){return (a.state.acks[ME]?1:0)-(b.state.acks[ME]?1:0)}).forEach(function(item){
      var acked=item.state.acks[ME],color=item.priority==='critical'?'var(--crit)':item.priority==='high'?'var(--warn)':'var(--g)';
      html+='<div class="ops-notif'+(acked?' acked':'')+'" style="border-left:3px solid '+color+'"><div class="ops-notif-icon"><span class="dot '+dot(item)+'"></span></div><div class="ops-notif-body">'+
        '<div class="ops-notif-text"><strong>'+esc(item.title)+'</strong>'+(item.body?' '+esc(item.body):'')+'</div>'+
        '<div class="ops-notif-time">'+esc(when(item.pushed_at))+(acked?' &middot; acknowledged '+esc(when(acked)):'')+'</div>'+
        (acked?'':'<div class="ops-actions"><button class="btn btn-sm btn-outline" onclick="opsAct('+item.id+',\'ack\')">Acknowledge</button></div>')+'</div></div>';
    });
    els.notices.innerHTML=html;
  }

  function render(items){
    renderTasks(items.filter(function(i){return i.kind==='task'}));
    renderChecklists(items.filter(function(i){return i.kind==='checklist'}));
    renderNotices(items.filter(function(i){return i.kind==='notice'}));
  }

  function load(){
    fetch(API+'/me',{credentials:'same-origin'}).then(checked).then(function(d){render(d.items||[])})
      .catch(function(e){['tasks','checklists','notices'].forEach(function(k){els[k].innerHTML='<div class="ops-empty">Could not load: '+esc(e.message)+'</div>'})});
  }

  window.opsAct=function(id,action,stepKey){
    fetch(API+'/items/'+id+'/events',{method:'POST',credentials:'same-origin',
      headers:{'Content-Type':'application/json','X-CSRFToken':CSRF},
      body:JSON.stringify({action:action,step_key:stepKey||null})})
      .then(checked).then(function(){toast('Saved');load()}).catch(function(e){toast('Error: '+e.message,true);load()});
  };

  load();
  setInterval(load,60000);
})();
```

- [ ] **Step 4: Run to verify it passes, and syntax-check the script**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ops_pages.py -q -p no:cacheprovider`
Expected: 1 passed.
Run: `node -e "new Function(require('fs').readFileSync('xissite/static/js/ops.js','utf8'));console.log('OK')"`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add xissite/templates/employee_ops.html xissite/static/js/ops.js tests/test_ops_pages.py
git commit -m "feat(ops): /ops renders pushed items and posts actions

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Admin dashboard Ops section

**Files:**
- Modify: `xissite/templates/admin_dashboard.html` (nav link after the Security link at line 41; new section card before the `<!-- Security -->` card at line 186)
- Modify: `xissite/static/js/admin_dashboard.js` (new functions; `fetchOps()` added to `refresh()`)
- Test: `tests/test_ops_pages.py` (append)

**Interfaces:**
- Consumes: `GET /api/admin/ops/items?status=all` (`{items, total}`), `DELETE /api/admin/ops/items/<ref>`; existing helpers `esc`, `checked`, `failToast`, `apiDelete`, `relTime`, `fullDate`, `showToast`, `API`.
- Produces: `#sec-ops` section, `fetchOps()`, `renderOps(items)`, `window.archiveOps(ref)`.

- [ ] **Step 1: Write the failing test** (append to `tests/test_ops_pages.py`)

```python
def test_admin_dashboard_has_ops_section(client, db):
    _login_as(client, db, 'boss', 'admin')
    html = client.get('/admin').data.decode()
    assert 'id="sec-ops"' in html
    assert 'href="#sec-ops"' in html
    assert 'id="ops-body"' in html
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ops_pages.py -q -p no:cacheprovider -k admin`
Expected: 1 failed.

- [ ] **Step 3: Add the section and the JS**

In `xissite/templates/admin_dashboard.html`, add after the Security nav link:

```html
  <a href="#sec-ops" data-sec="ops">Ops</a>
```

and insert this card immediately before the `<!-- Security -->` comment / `<div class="sec-card" id="sec-security">`:

```html
<!-- Ops content (pushed by TullOps) -->
<div class="sec-card" id="sec-ops">
  <div class="sec-hdr">
    <h2>// Ops Content <span class="sec-count" id="ops-count"></span></h2>
    <div class="tbl-wrap">
      <table class="table" id="ops-table" style="display:none">
        <thead><tr><th>Ref</th><th>Kind</th><th>Title</th><th>Assignee</th><th>Status</th><th>Progress</th><th>Updated</th><th>Actions</th></tr></thead>
        <tbody id="ops-body"></tbody>
      </table>
    </div>
    <div class="alert-none" id="ops-empty">Nothing pushed by TullOps yet</div>
  </div>
</div>
```

(Match the surrounding cards' inner markup: if the neighbouring section uses `<div class="sec-hdr">` differently, copy that section's wrapper exactly and keep the `id`s above.)

In `xissite/static/js/admin_dashboard.js`, add before the `// ---- Audit Log` comment:

```javascript
// ---- Ops content (pushed by TullOps) -------------------------------------
function fetchOps(){
  fetch(API+'/ops/items?status=all&limit=200').then(checked).then(function(d){renderOps(d.items||[])})
    .catch(function(e){var emp=document.getElementById('ops-empty');emp.style.display='block';emp.textContent='Failed to load ops items: '+e.message});
}
function opsProgress(item){
  var st=item.state||{};
  if(item.kind==='checklist'){var n=item.steps.filter(function(s){return st.steps&&st.steps[s.key]}).length;return n+' / '+item.steps.length+' steps'}
  if(item.kind==='notice'){return Object.keys(st.acks||{}).length+' acknowledged'}
  return item.status==='done'?'done by '+esc(st.done_by||''):'open';
}
function renderOps(items){
  var tb=document.getElementById('ops-body'),tbl=document.getElementById('ops-table'),emp=document.getElementById('ops-empty'),cnt=document.getElementById('ops-count');
  if(!items.length){tbl.style.display='none';emp.style.display='block';emp.textContent='Nothing pushed by TullOps yet';cnt.textContent='';return}
  emp.style.display='none';tbl.style.display='table';cnt.textContent='('+items.length+')';
  var html='';
  items.forEach(function(item){
    var sb=item.status==='done'?'badge-ok':item.status==='archived'?'badge-off':'badge-warn';
    html+='<tr>'+
      '<td style="font-family:Consolas,monospace;font-size:.8em">'+esc(item.ref)+'</td>'+
      '<td>'+esc(item.kind)+'</td>'+
      '<td title="'+esc(item.body||'')+'">'+esc(item.title)+'</td>'+
      '<td>'+(item.assignee?esc(item.assignee):'<span style="color:var(--mut)">everyone</span>')+'</td>'+
      '<td><span class="badge '+sb+'">'+esc(item.status)+'</span></td>'+
      '<td>'+opsProgress(item)+'</td>'+
      '<td title="'+esc(fullDate(item.updated_at))+'">'+relTime(item.updated_at)+'</td>'+
      '<td>'+(item.status==='archived'?'':'<button class="btn btn-sm btn-danger" onclick="archiveOps(\''+esc(item.ref)+'\')">Archive</button>')+'</td></tr>';
  });
  tb.innerHTML=html;
}
window.archiveOps=function(ref){if(confirm('Archive '+ref+'? Employees will no longer see it.'))apiDelete('/ops/items/'+encodeURIComponent(ref)).then(checked).then(function(){showToast('Archived');fetchOps()}).catch(failToast)};
```

and add `fetchOps();` as the last line inside `function refresh(){ ... }`.

- [ ] **Step 4: Run to verify it passes, and syntax-check**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ops_pages.py -q -p no:cacheprovider`
Expected: 2 passed.
Run: `node -e "new Function(require('fs').readFileSync('xissite/static/js/admin_dashboard.js','utf8'));console.log('OK')"`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add xissite/templates/admin_dashboard.html xissite/static/js/admin_dashboard.js tests/test_ops_pages.py
git commit -m "feat(ops): admin dashboard section listing pushed items

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Field-name contract for the new scripts

**Files:**
- Modify: `tests/test_panel_contract.py`

**Interfaces:**
- Consumes: the `shapes` fixture (`endpoint -> set of keys`), `_accesses(source, var)`, `JS_BUILTINS`.
- Produces: `SITE_CONTRACT` mapping site script paths to `{var: endpoint}`, and a parametrised test over it. Adds `/ops/items`, `/ops/events` (admin) and `/ops/me` (employee session) to the collected shapes.

- [ ] **Step 1: Extend the fixture and add the test** (edits to `tests/test_panel_contract.py`)

1. Add to `ENDPOINTS`: `'/ops/items?status=all'`, `'/ops/events'`.
2. In `_seed(db)`, after the user is added, push two items and one event so the shapes are populated. Add at the end of `_seed`:

```python
    from xissite.models import OpsItem, OpsEvent
    emp = User.query.filter_by(email='emp').one()
    task = OpsItem(ref='task:seed', kind='task', title='Seed task', assignee_id=emp.id, body='b')
    task.set_state(None)
    cl = OpsItem(ref='cl:seed', kind='checklist', title='Seed checklist')
    cl.set_steps([{'key': 'a', 'label': 'A'}])
    st = cl.get_state()
    st['steps']['a'] = {'by': 'emp', 'at': '2026-09-20T10:00:00+00:00'}
    st['acks'] = {'emp': '2026-09-20T10:00:00+00:00'}
    cl.set_state(st)
    db.session.add_all([task, cl])
    db.session.flush()
    db.session.add(OpsEvent(item_id=task.id, item_ref=task.ref, user_id=emp.id,
                            username='emp', action='complete', note='n'))
    db.session.commit()
```

3. In the `shapes` fixture, after the admin loop and before the reply POST, collect the employee endpoint by logging in as `emp` (password is `'x' * 10` in `_seed`):

```python
        client.post('/login', data={'username': 'emp', 'password': 'x' * 10})
        from flask import g
        g.pop('_login_user', None)
        resp = client.get('/api/ops/me')
        assert resp.status_code == 200, resp.data[:200]
        result['/ops/me'] = _keys(resp.get_json(), set())
        client.get('/logout')
        g.pop('_login_user', None)
```

   Note: `_keys` walks dict keys, so the step key `'a'` and the username `'emp'` inside `state.steps` / `state.acks` also land in the set. That is harmless.

4. Add the site-script contract and its test after the existing template test:

```python
SITE_CONTRACT = {
    'xissite/static/js/ops.js': {'item': '/ops/me', 'step': '/ops/me'},
    'xissite/static/js/admin_dashboard.js': {'item': '/ops/items?status=all'},
}


@pytest.mark.parametrize('script', sorted(SITE_CONTRACT))
def test_site_script_reads_only_keys_the_api_sends(shapes, script):
    source = (REPO / script).read_text(encoding='utf-8')
    bad = []
    for var, endpoint in SITE_CONTRACT[script].items():
        allowed = shapes[endpoint] | JS_BUILTINS
        for key in sorted(_accesses(source, var) - allowed):
            bad.append(f'{var}.{key} (not in {endpoint})')
    assert not bad, f'{script} reads keys the API does not send:\n  ' + '\n  '.join(bad)
```

- [ ] **Step 2: Run to verify it passes** (this test is a guard; it should pass against the scripts written in Tasks 6 and 7. If it reports a key, the script is wrong, not the test: fix the script.)

Run: `.venv\Scripts\python.exe -m pytest tests/test_panel_contract.py -q -p no:cacheprovider`
Expected: all passed, including 2 new.

- [ ] **Step 3: Prove the guard bites**

Temporarily change `item.title` to `item.titel` in `ops.js`, run the test, confirm it fails naming `item.titel`, then revert the change. Do not commit the typo.

- [ ] **Step 4: Commit**

```bash
git add tests/test_panel_contract.py
git commit -m "test(ops): pin ops.js and dashboard field names to the API

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: Contract document for TullOps, docs, and the architecture map note

**Files:**
- Create: `docs/ops-content-push.md`
- Modify: `README.md` (route table: add the ops endpoints; Admin Tools: mention the Ops section)
- Modify: `MANAGEMENT_GUIDE.md` (User Management: one paragraph on pushed content)

- [ ] **Step 1: Write `docs/ops-content-push.md`**

```markdown
# Ops content push: the contract TullOps codes against

TullSite stores tasks, checklists and notices that TullOps pushes, shows
each to the right employee at `/ops`, and records what they did. TullOps
polls those actions back. Auth is the existing `Authorization: Bearer
<ADMIN_API_KEY>`. Design: `docs/superpowers/specs/2026-09-20-ops-content-push-design.md`.

## Push (idempotent)

`PUT /api/admin/ops/items/<ref>` where `<ref>` is your own id (e.g. the
kanban task id). Create returns 201, update 200; either way the body is the
item as stored.

```json
{
  "kind": "checklist",              // task | checklist | notice   (required on create)
  "title": "Morning startup, Tower 7",   // required on create, <= 200 chars
  "body": "Do these before 09:00.",      // optional, <= 4000 chars, plain text
  "steps": [                              // checklist only, <= 50, keys unique
    {"key": "power", "label": "Power on pumps"},
    {"key": "ec", "label": "Log EC reading"}
  ],
  "assignee": "patrick",                  // site username, must be active; null = everyone
  "priority": "high",                     // low | normal | high | critical (default normal)
  "due_at": "2026-09-21T13:00:00Z",       // ISO 8601, optional
  "status": "open",                       // open | done (archive with DELETE)
  "reset_state": false                    // true wipes ticks/completion and reopens
}
```

Omitted fields keep their current values. A re-push never wipes what an
employee has done unless `reset_state` is true. Changing `steps` keeps
ticks for keys that still exist.

Errors: 400 with `{"error": "..."}` for bad input; 404 if the assignee
does not exist or is not active.

## List and archive

- `GET /api/admin/ops/items?assignee=&kind=&status=` (status defaults to
  everything except archived; `status=all` includes archived; `limit` <= 500)
- `DELETE /api/admin/ops/items/<ref>` archives. Employees stop seeing it;
  events stay.

## Poll actions back

`GET /api/admin/ops/events?after=<cursor>&limit=200`

```json
{"events": [
   {"id": 12, "item_id": 3, "item_ref": "task:7", "username": "patrick",
    "action": "tick", "step_key": "ec", "note": null, "created_at": "2026-09-21T12:40:11+00:00"}
 ],
 "next_after": 12,
 "reset": false}
```

Actions: `complete`, `reopen` (tasks and checklists), `tick`, `untick`
(checklists, with `step_key`), `ack` (notices). Persist `next_after` and
send it as `after` next time. Poll every minute or so.

## When `reset` is true

The site's database was emptied since you last polled (it lives in
App Engine's per-instance temp storage until Cloud SQL). The response
starts from the beginning. Do this:

1. Re-push every open item with `PUT` (idempotent).
2. Set your cursor to `next_after`.

Also re-push all open items on a schedule (hourly is fine). It is a no-op
when nothing changed, and it means a wipe costs at most an hour of content.

## Employee side, for reference

Employees see `/ops` after logging in. It reads `GET /api/ops/me` and
posts to `POST /api/ops/items/<id>/events` with `{"action": ..., "step_key": ..., "note": ...}`
using their session. TullOps never calls these.
```

- [ ] **Step 2: README and guide**

In `README.md`, add to the Admin API table:

```markdown
| Ops content | `PUT /ops/items/<ref>` · `GET /ops/items` · `DELETE /ops/items/<ref>` · `GET /ops/events?after=` (see `docs/ops-content-push.md`) |
```

and under `### Login required` add `- `GET /api/ops/me`, `POST /api/ops/items/<id>/events` - Employee's pushed items and actions (session + CSRF header)`. In the Admin Tools section, append to the `/admin` bullet: ", and an Ops section listing what TullOps has pushed to each employee."

In `MANAGEMENT_GUIDE.md`, after `### Managing Users`, add:

```markdown
### Pushing work to employees

TullOps pushes tasks, checklists and notices to employees through
`/api/admin/ops` and polls their actions back from `/api/admin/ops/events`.
Employees see their items at `/ops`. The contract is in
`docs/ops-content-push.md`. Until the site moves to Cloud SQL, a deploy or
restart empties pushed content; TullOps re-pushes on the `reset` signal and
on a schedule.
```

- [ ] **Step 3: Run both suites, then commit**

Run: `.venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider`
Expected: all passed.
Run: `.venv-admin\Scripts\python.exe -m pytest admin_panel/tests/ -q -p no:cacheprovider`
Expected: 76 passed (unchanged).

```bash
git add docs/ops-content-push.md README.md MANAGEMENT_GUIDE.md
git commit -m "docs(ops): contract for TullOps, README and guide updates

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: Live check, merge, deploy

**Files:** none new.

- [ ] **Step 1: Run the local site and exercise the loop end to end**

With `vars.env` in place, from the repo root:

```bash
.venv\Scripts\python.exe main.py
```

In another shell (key from `vars.env`):

```bash
curl -s -X PUT http://127.0.0.1:5000/api/admin/ops/items/demo:1 -H "Authorization: Bearer <ADMIN_API_KEY>" -H "Content-Type: application/json" -d "{\"kind\":\"checklist\",\"title\":\"Demo\",\"steps\":[{\"key\":\"a\",\"label\":\"First\"},{\"key\":\"b\",\"label\":\"Second\"}]}"
```

Expected: 201 JSON with `"ref":"demo:1"`. Log in at http://localhost:5000/login as the bootstrap admin, open http://localhost:5000/ops, tick both steps, click Mark done. Then:

```bash
curl -s http://127.0.0.1:5000/api/admin/ops/events -H "Authorization: Bearer <ADMIN_API_KEY>"
```

Expected: three events (`tick`, `tick`, `complete`) and `"reset": false`. Open http://localhost:5000/admin and confirm the Ops section shows `demo:1` as done, then Archive it and confirm it disappears from `/ops`.

- [ ] **Step 2: Merge and push**

```bash
git checkout main
git merge --ff-only feat/ops-content-push
git push origin main
```

- [ ] **Step 3: Deploy** (only with the user's go-ahead; the site also carries the unreleased order-total change)

```bash
gcloud app deploy app.yaml --project xissite-355821 --quiet
```

Then verify: `curl -s -o /dev/null -w "%{http_code}" https://tullhydro.com/api/admin/ops/events` should print `401` (route exists, key required), and delete the superseded App Engine version.

---

## Self-review

**Spec coverage.** Data model → Task 1. Admin API upsert/list/archive → Task 3; events + reset → Task 4. Employee API and per-kind rules → Task 5. `/ops` page → Task 6. Admin dashboard Ops section → Task 7. Contract test extension → Task 8. TullOps contract doc → Task 9. Errors and limits: `BadRequest` handlers via `json_errors` (Task 2), 404-not-403 for invisible items (Task 5), length caps (Tasks 3 and 5), events cap (Task 4), `as_utc` on every datetime out (Task 1 `to_dict`, Task 3 `_parse_due`). Auth: Bearer or admin session on `/api/admin/ops` via `require_api_key`; employee session + CSRF on `/api/ops` via `require_employee_session` (Task 5); tests in Task 3 (employee session rejected) and Task 5 (anonymous and Bearer rejected). Audit on push and archive → Task 3.

**Placeholders.** None: every step has its code or its exact command.

**Type consistency.** `OpsItem.set_state(None)` resets to `empty_state()` (Task 1) and is used that way in Tasks 3 and 8. `to_dict()['state']` always has `steps` and `acks` dicts, which `ops.js` and the dashboard rely on. `_int_arg` keeps its name in `admin_api.py` so the existing AST-based param contract still finds it. `apply_action` sets `step_key` only for tick/untick, matching the events test. `_login` helpers in Tasks 5 and 6 drop `g._login_user`, the same workaround already used in `tests/test_suspension.py`.
