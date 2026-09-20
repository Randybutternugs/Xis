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
    if not isinstance(username, str) or not username.strip():
        raise BadRequest('assignee must be a username string or null')
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
        if step_key is not None and not isinstance(step_key, str):
            raise BadRequest('step_key must be a string')
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
    if not isinstance(data, dict):
        raise BadRequest('body must be a JSON object')
    action = data.get('action')
    if action not in OpsEvent.ACTIONS:
        raise BadRequest('action must be one of complete, reopen, tick, untick, ack')
    apply_action(item, current_user, action, data.get('step_key'), data.get('note'))
    db.session.commit()
    return jsonify(item.to_dict())
