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


def test_ops_js_never_inlines_api_strings_into_event_handlers():
    """HTML-entity escaping is undone before an inline handler's JS is parsed, so
    only a numeric id may be interpolated into an on*="..." attribute; any other
    interpolated expression (e.g. a string field) must reach handlers via data-*
    attributes instead."""
    import re
    from pathlib import Path
    for rel in ('xissite/static/js/ops.js', 'xissite/static/js/admin_dashboard.js'):
        src = Path(rel).read_text(encoding='utf-8')
        for m in re.finditer(r'on(?:click|change)="([^"]*)"', src):
            attr = m.group(1)
            for expr in re.findall(r"'\+(.+?)\+'", attr):
                assert re.fullmatch(r'[A-Za-z_]\w*\.id', expr.strip()), \
                    rel + ': ' + expr + ' in ' + m.group(0)


def test_admin_dashboard_has_ops_section(client, db):
    _login_as(client, db, 'boss', 'admin')
    html = client.get('/admin').data.decode()
    assert 'id="sec-ops"' in html
    assert 'href="#sec-ops"' in html
    assert 'id="ops-body"' in html
