"""Contract between the local admin panel's pages and this API.

The panel (admin_panel/) renders JSON from /api/admin/* by string-building
HTML in each template's inline script. Nothing else ties a template's
field names to the API, and the first version of the panel shipped with
most pages reading keys the API never sends. This test seeds one of each
entity, calls every endpoint the panel uses, collects the keys that
actually come back, and fails if a template reads a key that is not there
or sends a query parameter the endpoint does not read.

To add a page or a JSON variable, extend CONTRACT below.
"""

import ast
import os
import re
from pathlib import Path

import pytest

os.environ['ADMIN_API_KEY'] = 'test-api-key-for-dual-auth'
API = {'Authorization': 'Bearer test-api-key-for-dual-auth'}

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = REPO / 'admin_panel' / 'templates'
ADMIN_API_SRC = REPO / 'xissite' / 'admin_api.py'

# Endpoints the panel reads. /customers/<id> is exercised as /customers/1.
ENDPOINTS = [
    '/stats', '/users', '/login-attempts', '/customers', '/customers/1',
    '/purchases', '/purchases/stats', '/feedback', '/feedback/stats',
    '/visitors', '/visitors/recent', '/security/alerts', '/security/audit-log',
    '/banned-ips', '/security/login-heatmap', '/visitors/heatmap',
    '/customers/stats', '/customers/geo', '/purchases/geo', '/purchases/funnel',
    '/visitors/referrers', '/visitors/pageflow', '/visitors/devices',
]

# Per template: JS variable name -> endpoint whose response it holds.
# A variable mapped to a list of endpoints may hold any of them.
ALL = ENDPOINTS
CONTRACT = {
    'site_admin_feedback.html': {'fb': '/feedback', 'stats': '/stats'},
    'site_admin_customers.html': {'cust': '/customers', 'detail': '/customers/1',
                                  'pur': '/customers/1', 'stats': '/stats'},
    'site_admin_logins.html': {'att': '/login-attempts', 'l24': '/stats',
                               'susp': '/security/alerts'},
    'site_admin_purchases.html': {'pur': '/purchases'},
    'site_admin_security.html': {'bf': '/security/alerts', 'susp': '/security/alerts',
                                 'fu': '/security/alerts', 'l24': '/stats'},
    'site_admin_users.html': {'usr': '/users'},
    'site_admin_visitors.html': {'stats': '/visitors', 'day': '/visitors',
                                 'page': '/visitors', 'ref': '/visitors',
                                 'visit': '/visitors/recent'},
    # The dashboard reuses short names across many endpoints; hold it to the
    # union so a key that exists nowhere in the API still fails.
    'site_admin_dashboard.html': {
        'd': ALL, 'x': ALL, 's': ALL, 'f': '/feedback', 'u': '/users',
        'p': ALL, 'c': ['/customers', '/customers/1'], 'b': '/banned-ips',
        'a': ['/login-attempts', '/security/audit-log', '/stats'],
        'l24': '/stats', 'res': '/feedback/stats',
        'brute': '/security/alerts', 'susp': '/security/alerts',
        'fuser': '/security/alerts', 'seq': '/visitors/pageflow',
    },
}

# Query parameters each template sends, per endpoint. The endpoint must
# read every one of them (request.args.get('<name>')).
PARAMS_SENT = {
    'site_admin_feedback.html': {'/feedback': {'type', 'resolved'}},
    'site_admin_customers.html': {'/customers': {'search'}},
    'site_admin_logins.html': {'/login-attempts': {'success', 'ip', 'from', 'to'}},
    'site_admin_purchases.html': {'/purchases': {'status', 'from', 'to'}},
    'site_admin_users.html': {'/users': {'status', 'user_type'}},
    'site_admin_visitors.html': {'/visitors': {'days'}},
}

# Property names that are JavaScript, not API data.
JS_BUILTINS = {
    'length', 'map', 'filter', 'forEach', 'slice', 'join', 'sort', 'reduce',
    'some', 'every', 'find', 'indexOf', 'includes', 'push', 'concat', 'keys',
    'entries', 'toFixed', 'toLowerCase', 'toUpperCase', 'trim', 'split',
    'replace', 'substring', 'charAt', 'startsWith', 'endsWith', 'style',
    'classList', 'textContent', 'innerHTML', 'value', 'ok', 'json', 'status',
    'statusText', 'error', 'message', 'then', 'catch', 'hasOwnProperty',
    'toString', 'toLocaleString', 'toLocaleDateString', 'getTime',
}


def _keys(obj, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(k)
            _keys(v, out)
    elif isinstance(obj, list):
        for item in obj:
            _keys(item, out)
    return out


def _seed(db):
    """One of each entity, plus enough failed logins to populate alerts."""
    from datetime import datetime, timezone
    from werkzeug.security import generate_password_hash
    from xissite.models import (Customer, Purchase_info, FeedBack, LoginAttempt,
                                BannedIP, SiteVisit, AdminAuditLog, User)
    db.session.add(User(email='emp', password=generate_password_hash('x' * 10),
                        user_type='employee', status='active', display_name='Emp'))
    c = Customer(email='c@x.co', name='Cus Tomer')
    db.session.add(c)
    db.session.flush()
    db.session.add(Purchase_info(customer_id=c.id, city='Austin', state='TX',
                                 country='US', line1='1 St', postal_code='78701',
                                 pay_status='paid'))
    db.session.add(FeedBack(feedbackmail='a@b.co', feedbacktype='General',
                            feedbackfullfield='hello there friend',
                            submitter_ip='1.2.3.4'))
    for _ in range(6):
        db.session.add(LoginAttempt(ip_address='1.2.3.4', user_agent='UA',
                                    username_attempted='x', success=False,
                                    failure_reason='invalid_password'))
    db.session.add(BannedIP(ip_address='9.9.9.9', reason='r', banned_by='auto', active=True))
    # Two visits from one IP inside the 30-minute session window populate
    # pageflow's top_sequences.
    db.session.add(SiteVisit(ip_address='1.2.3.4', path='/',
                             referrer='https://g.com/', user_agent='UA'))
    db.session.add(SiteVisit(ip_address='1.2.3.4', path='/sell',
                             referrer='', user_agent='UA'))
    db.session.add(AdminAuditLog(action='user.create', target_type='user',
                                 target_id='1', details='{}', admin_ip='127.0.0.1'))
    db.session.commit()


@pytest.fixture(scope='module')
def shapes(app):
    """endpoint -> set of every key anywhere in its JSON response."""
    from xissite import db as _db
    with app.app_context():
        _db.create_all()
        _seed(_db)
        client = app.test_client()
        result = {}
        for ep in ENDPOINTS:
            resp = client.get('/api/admin' + ep, headers=API)
            assert resp.status_code == 200, f'{ep} returned {resp.status_code}: {resp.data[:200]}'
            result[ep] = _keys(resp.get_json(), set())
        # The one POST whose response a page reads: reply to feedback.
        # Postmark is stubbed so no email leaves the test.
        from unittest.mock import patch
        os.environ['POSTMARK_SERVER_TOKEN'] = 'x'
        os.environ['POSTMARK_SENDER_EMAIL'] = 's@t.co'
        with patch('requests.post') as post:
            post.return_value.status_code = 200
            resp = client.post('/api/admin/feedback/1/reply', headers=API,
                               json={'message': 'hi'})
        assert resp.status_code == 200, resp.data[:200]
        result['/feedback/1/reply'] = _keys(resp.get_json(), set())
        result['/feedback'] |= result['/feedback/1/reply']
        _db.session.rollback()
        _db.drop_all()
    return result


def _accesses(source, var):
    return set(re.findall(r'\b' + re.escape(var) + r'\.([A-Za-z_][A-Za-z0-9_]*)', source))


@pytest.mark.parametrize('template', sorted(CONTRACT))
def test_template_reads_only_keys_the_api_sends(shapes, template):
    source = (TEMPLATES / template).read_text(encoding='utf-8')
    bad = []
    for var, endpoints in CONTRACT[template].items():
        if isinstance(endpoints, str):
            endpoints = [endpoints]
        allowed = set().union(*(shapes[e] for e in endpoints)) | JS_BUILTINS
        for key in sorted(_accesses(source, var) - allowed):
            bad.append(f'{var}.{key} (not in {", ".join(endpoints) if len(endpoints) < 4 else "any endpoint"})')
    assert not bad, f'{template} reads keys the API does not send:\n  ' + '\n  '.join(bad)


def _args_read_by_route():
    """route path -> set of request.args.get('<name>') the handler reads."""
    tree = ast.parse(ADMIN_API_SRC.read_text(encoding='utf-8'))
    routes = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        paths = []
        for dec in node.decorator_list:
            if (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                    and dec.func.attr == 'route' and dec.args):
                paths.append(dec.args[0].value)
        if not paths:
            continue
        names = set()
        for sub in ast.walk(node):
            if not (isinstance(sub, ast.Call) and sub.args and isinstance(sub.args[0], ast.Constant)):
                continue
            # request.args.get('name', ...)
            if (isinstance(sub.func, ast.Attribute) and sub.func.attr == 'get'
                    and isinstance(sub.func.value, ast.Attribute)
                    and sub.func.value.attr == 'args'):
                names.add(sub.args[0].value)
            # _int_arg('name', default, ...) reads request.args unless source= is given
            elif (isinstance(sub.func, ast.Name) and sub.func.id == '_int_arg'
                    and not any(k.arg == 'source' for k in sub.keywords)):
                names.add(sub.args[0].value)
        for p in paths:
            routes.setdefault(p, set()).update(names)
    return routes


@pytest.mark.parametrize('template', sorted(PARAMS_SENT))
def test_template_sends_only_params_the_endpoint_reads(template):
    routes = _args_read_by_route()
    bad = []
    for endpoint, sent in PARAMS_SENT[template].items():
        read = routes.get(endpoint, set())
        for name in sorted(sent - read):
            bad.append(f'{endpoint}?{name} (handler reads: {sorted(read) or "nothing"})')
    assert not bad, f'{template} sends params the API ignores:\n  ' + '\n  '.join(bad)


@pytest.mark.parametrize('template', sorted(PARAMS_SENT))
def test_template_actually_sends_declared_params(template):
    """Keep PARAMS_SENT honest: each declared name must appear in the template."""
    source = (TEMPLATES / template).read_text(encoding='utf-8')
    for endpoint, sent in PARAMS_SENT[template].items():
        for name in sent:
            assert re.search(r"['\"]" + re.escape(name) + r"['\"]|[?&]" + re.escape(name) + r"=", source), \
                f'{template} declares it sends {endpoint}?{name} but never does'
