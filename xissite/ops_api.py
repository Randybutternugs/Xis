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
