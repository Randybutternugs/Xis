# Auth System Security Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate TullSite from env-var credential hashes to database-backed multi-user auth with session hardening, rate limiting, and account lockout.

**Architecture:** The login route validates against the User table (not env vars). TullOps manages accounts remotely via the admin API. Roles are `admin` and `employee` only (investor removed). Rate limiting and lockout protect against brute force. Session cookies are hardened for production.

**Tech Stack:** Flask 3.0, Flask-Login 0.6.3, Flask-SQLAlchemy 3.1.1, Werkzeug 3.0.1 (scrypt hashing), SQLite, pytest

**Spec:** `docs/superpowers/specs/2026-03-29-auth-system-security-overhaul-design.md`

---

### Task 1: Set Up Test Infrastructure

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/__init__.py`
- Create: `tests/test_smoke.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add pytest to requirements.txt**

Add at the bottom of `requirements.txt`:

```
# Testing
pytest==8.0.0
```

- [ ] **Step 2: Create tests/__init__.py**

```python
```

Empty file, makes `tests/` a package.

- [ ] **Step 3: Create tests/conftest.py**

```python
import os
import pytest

# Set test env vars before importing app
os.environ['FLASK_SECRET_KEY'] = 'test-secret-key-for-testing-only'
os.environ['ADMIN_BOOTSTRAP_EMAIL'] = 'admin'
os.environ['ADMIN_BOOTSTRAP_PASSWORD'] = 'testpassword123'
os.environ['FLASK_ENV'] = 'development'

from xissite import create_app, db as _db


@pytest.fixture(scope='session')
def app():
    """Create a Flask app configured for testing."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SERVER_NAME'] = 'localhost'
    return app


@pytest.fixture(scope='function')
def db(app):
    """Provide a clean database for each test."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.rollback()
        _db.drop_all()


@pytest.fixture(scope='function')
def client(app, db):
    """Provide a Flask test client with a clean database."""
    with app.test_client() as client:
        with app.app_context():
            yield client
```

- [ ] **Step 4: Create tests/test_smoke.py**

```python
def test_app_creates(app):
    """App factory returns a Flask app."""
    assert app is not None
    assert app.config['TESTING'] is True


def test_index_loads(client):
    """Public homepage returns 200."""
    response = client.get('/')
    assert response.status_code == 200
```

- [ ] **Step 5: Run tests to verify infrastructure works**

Run: `cd C:/Users/adoni/Desktop/TullSite && python -m pytest tests/test_smoke.py -v`
Expected: 2 tests PASS

- [ ] **Step 6: Commit**

```bash
git add tests/ requirements.txt
git commit -m "Add pytest test infrastructure with app fixture and smoke tests"
```

---

### Task 2: Add Supporting Models to models.py

The admin API (`admin_api.py`) imports `LoginAttempt`, `SiteVisit`, `BannedIP`, `GeoIPCache`, and `AdminAuditLog` from `.models`, but these don't exist yet. The `User` and `FeedBack` models are also missing fields and `to_dict()` methods that admin_api.py depends on.

**Files:**
- Modify: `xissite/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for new models**

Create `tests/test_models.py`:

```python
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash


def test_user_new_fields(db):
    """User model has status, display_name, failed_attempts, locked_until, etc."""
    from xissite.models import User

    user = User(
        email='patrick@tull.com',
        password=generate_password_hash('testpass123'),
        user_type='employee',
        status='active',
        display_name='Patrick T.',
        notes='Cofounder',
        failed_attempts=0,
    )
    db.session.add(user)
    db.session.commit()

    fetched = User.query.filter_by(email='patrick@tull.com').first()
    assert fetched.status == 'active'
    assert fetched.display_name == 'Patrick T.'
    assert fetched.failed_attempts == 0
    assert fetched.locked_until is None
    assert fetched.created_at is not None


def test_user_to_dict(db):
    """User.to_dict() returns expected fields without password."""
    from xissite.models import User

    user = User(
        email='jake@tull.com',
        password=generate_password_hash('testpass123'),
        user_type='admin',
        display_name='Jake R.',
    )
    db.session.add(user)
    db.session.commit()

    d = user.to_dict()
    assert d['email'] == 'jake@tull.com'
    assert d['user_type'] == 'admin'
    assert d['display_name'] == 'Jake R.'
    assert 'password' not in d


def test_login_attempt_model(db):
    """LoginAttempt stores login attempt data."""
    from xissite.models import LoginAttempt

    attempt = LoginAttempt(
        ip_address='192.168.1.1',
        user_agent='Mozilla/5.0',
        username_attempted='admin',
        success=False,
        failure_reason='invalid_password',
    )
    db.session.add(attempt)
    db.session.commit()

    fetched = LoginAttempt.query.first()
    assert fetched.ip_address == '192.168.1.1'
    assert fetched.success is False
    assert fetched.to_dict()['username_attempted'] == 'admin'


def test_banned_ip_model(db):
    """BannedIP stores IP bans with expiry."""
    from xissite.models import BannedIP

    ban = BannedIP(
        ip_address='10.0.0.1',
        reason='Brute force',
        banned_by='auto',
        active=True,
    )
    db.session.add(ban)
    db.session.commit()

    fetched = BannedIP.query.first()
    assert fetched.active is True
    assert fetched.to_dict()['ip_address'] == '10.0.0.1'


def test_admin_audit_log_model(db):
    """AdminAuditLog records admin actions."""
    from xissite.models import AdminAuditLog

    entry = AdminAuditLog(
        action='user.create',
        target_type='user',
        target_id='5',
        admin_ip='127.0.0.1',
    )
    db.session.add(entry)
    db.session.commit()

    fetched = AdminAuditLog.query.first()
    assert fetched.action == 'user.create'
    assert fetched.to_dict()['target_type'] == 'user'


def test_feedback_new_fields(db):
    """FeedBack model has resolved, admin_notes, serial_number, etc."""
    from xissite.models import FeedBack

    fb = FeedBack(
        feedbackmail='customer@example.com',
        feedbacktype='1',
        feedbackfullfield='Great product!',
        resolved=False,
    )
    db.session.add(fb)
    db.session.commit()

    fetched = FeedBack.query.first()
    assert fetched.resolved is False
    assert fetched.admin_notes is None
    assert fetched.to_dict()['feedbackmail'] == 'customer@example.com'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL (missing fields, missing to_dict methods)

- [ ] **Step 3: Update User model with new fields and to_dict()**

In `xissite/models.py`, replace the entire User class (lines 52-77):

```python
class User(db.Model, UserMixin):
    """
    User model for admin and employee authentication.

    Supports multiple user types:
    - 'admin': Full access to database viewer, customer info, feedback
    - 'employee': Access to TullOps-assigned content only

    Accounts are managed by TullOps via the admin API.
    """
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(256))
    user_type = db.Column(db.String(50), default='employee')
    status = db.Column(db.String(50), default='active')
    display_name = db.Column(db.String(150))
    notes = db.Column(db.Text)
    last_login = db.Column(db.DateTime)
    failed_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'user_type': self.user_type,
            'status': self.status,
            'display_name': self.display_name,
            'notes': self.notes,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'failed_attempts': self.failed_attempts,
            'locked_until': self.locked_until.isoformat() if self.locked_until else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<User {self.id} - {self.user_type}>'
```

- [ ] **Step 4: Update FeedBack model with new fields and to_dict()**

In `xissite/models.py`, replace the FeedBack class (lines 23-46):

```python
class FeedBack(db.Model):
    """
    Stores customer feedback submissions from the contact form.
    """
    __tablename__ = 'feed_back'

    id = db.Column(db.Integer, primary_key=True)
    feedbackmail = db.Column(db.String(150))
    feedbacktype = db.Column(db.String(50))
    feedbackorderid = db.Column(db.String(50), nullable=True)
    feedbackfullfield = db.Column(db.String(10000))
    date = db.Column(db.DateTime(timezone=True), default=func.now())
    submitter_ip = db.Column(db.String(45), nullable=True)
    resolved = db.Column(db.Boolean, default=False)
    admin_notes = db.Column(db.Text)
    serial_number = db.Column(db.String(100))
    first_response_date = db.Column(db.DateTime)
    resolved_date = db.Column(db.DateTime)
    resolution_time_hours = db.Column(db.Integer)

    def to_dict(self):
        return {
            'id': self.id,
            'feedbackmail': self.feedbackmail,
            'feedbacktype': self.feedbacktype,
            'feedbackorderid': self.feedbackorderid,
            'feedbackfullfield': self.feedbackfullfield,
            'date': self.date.isoformat() if self.date else None,
            'submitter_ip': self.submitter_ip,
            'resolved': self.resolved,
            'admin_notes': self.admin_notes,
            'serial_number': self.serial_number,
            'first_response_date': self.first_response_date.isoformat() if self.first_response_date else None,
            'resolved_date': self.resolved_date.isoformat() if self.resolved_date else None,
            'resolution_time_hours': self.resolution_time_hours,
        }

    def __repr__(self):
        return f'<FeedBack {self.id} - {self.feedbackmail}>'
```

- [ ] **Step 5: Add to_dict() to Customer and Purchase_info**

Add `to_dict()` method to Customer class after `__repr__` (after line 106):

```python
    def to_dict(self, include_purchases=False):
        d = {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'creation_date': self.creation_date.isoformat() if self.creation_date else None,
        }
        if include_purchases:
            d['purchases'] = [p.to_dict() for p in self.buys] if self.buys else []
        return d
```

Add `to_dict()` method to Purchase_info class after `__repr__` (after line 142):

```python
    def to_dict(self):
        return {
            'id': self.id,
            'product_name': self.product_name,
            'city': self.city,
            'country': self.country,
            'line1': self.line1,
            'line2': self.line2,
            'postal_code': self.postal_code,
            'state': self.state,
            'pay_status': self.pay_status,
            'purchase_date': self.purchase_date.isoformat() if self.purchase_date else None,
            'customer_id': self.customer_id,
        }
```

- [ ] **Step 6: Add LoginAttempt model**

Add after the User class in `xissite/models.py`:

```python
# ============================================================================
# LOGIN ATTEMPT MODEL (Security Tracking)
# ============================================================================
class LoginAttempt(db.Model):
    """Records every login attempt for security monitoring."""
    __tablename__ = 'login_attempt'

    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    username_attempted = db.Column(db.String(150))
    success = db.Column(db.Boolean, default=False)
    failure_reason = db.Column(db.String(100))
    user_type_matched = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime(timezone=True), default=func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'username_attempted': self.username_attempted,
            'success': self.success,
            'failure_reason': self.failure_reason,
            'user_type_matched': self.user_type_matched,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }

    def __repr__(self):
        return f'<LoginAttempt {self.id} - {"OK" if self.success else "FAIL"}>'
```

- [ ] **Step 7: Add BannedIP model**

Add after LoginAttempt in `xissite/models.py`:

```python
# ============================================================================
# BANNED IP MODEL (Security)
# ============================================================================
class BannedIP(db.Model):
    """Tracks banned IP addresses."""
    __tablename__ = 'banned_ip'

    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False)
    reason = db.Column(db.String(200))
    banned_by = db.Column(db.String(50))
    active = db.Column(db.Boolean, default=True)
    created_date = db.Column(db.DateTime(timezone=True), default=func.now())
    expires_at = db.Column(db.DateTime)

    def to_dict(self):
        return {
            'id': self.id,
            'ip_address': self.ip_address,
            'reason': self.reason,
            'banned_by': self.banned_by,
            'active': self.active,
            'created_date': self.created_date.isoformat() if self.created_date else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
        }

    def __repr__(self):
        return f'<BannedIP {self.ip_address} active={self.active}>'
```

- [ ] **Step 8: Add SiteVisit, GeoIPCache, and AdminAuditLog models**

Add after BannedIP in `xissite/models.py`:

```python
# ============================================================================
# SITE VISIT MODEL (Analytics)
# ============================================================================
class SiteVisit(db.Model):
    """Tracks page visits for analytics."""
    __tablename__ = 'site_visit'

    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45))
    path = db.Column(db.String(500))
    referrer = db.Column(db.String(500))
    user_agent = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime(timezone=True), default=func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'ip_address': self.ip_address,
            'path': self.path,
            'referrer': self.referrer,
            'user_agent': self.user_agent,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }

    def __repr__(self):
        return f'<SiteVisit {self.path}>'


# ============================================================================
# GEO IP CACHE MODEL (Security)
# ============================================================================
class GeoIPCache(db.Model):
    """Caches geo-IP lookups to avoid repeated API calls."""
    __tablename__ = 'geo_ip_cache'

    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), unique=True, nullable=False)
    country = db.Column(db.String(100))
    region = db.Column(db.String(100))
    city = db.Column(db.String(100))
    isp = db.Column(db.String(200))
    cached_at = db.Column(db.DateTime(timezone=True), default=func.now())

    def to_dict(self):
        return {
            'ip_address': self.ip_address,
            'country': self.country,
            'region': self.region,
            'city': self.city,
            'isp': self.isp,
        }

    def __repr__(self):
        return f'<GeoIPCache {self.ip_address}>'


# ============================================================================
# ADMIN AUDIT LOG MODEL (Security)
# ============================================================================
class AdminAuditLog(db.Model):
    """Records admin API actions for audit trail."""
    __tablename__ = 'admin_audit_log'

    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.String(50))
    details = db.Column(db.Text)
    admin_ip = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime(timezone=True), default=func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'action': self.action,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'details': self.details,
            'admin_ip': self.admin_ip,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }

    def __repr__(self):
        return f'<AdminAuditLog {self.action}>'
```

- [ ] **Step 9: Run model tests**

Run: `python -m pytest tests/test_models.py -v`
Expected: All 6 tests PASS

- [ ] **Step 10: Commit**

```bash
git add xissite/models.py tests/test_models.py
git commit -m "Add security models and update User/FeedBack with new fields and to_dict()"
```

---

### Task 3: Add Database Migrations

Existing databases need ALTER TABLE statements for the new columns. The migration system already exists in `xissite/__init__.py:run_migrations()`.

**Files:**
- Modify: `xissite/__init__.py:240-281` (run_migrations function)

- [ ] **Step 1: Add migrations for User model new columns**

In `xissite/__init__.py`, add to the `migrations` list in `run_migrations()` (after the existing `add_feedback_submitter_ip` entry):

```python
        {
            'name': 'add_user_status',
            'check': "SELECT * FROM pragma_table_info('user') WHERE name='status'",
            'migrate': "ALTER TABLE user ADD COLUMN status VARCHAR(50) DEFAULT 'active'"
        },
        {
            'name': 'add_user_display_name',
            'check': "SELECT * FROM pragma_table_info('user') WHERE name='display_name'",
            'migrate': "ALTER TABLE user ADD COLUMN display_name VARCHAR(150)"
        },
        {
            'name': 'add_user_notes',
            'check': "SELECT * FROM pragma_table_info('user') WHERE name='notes'",
            'migrate': "ALTER TABLE user ADD COLUMN notes TEXT"
        },
        {
            'name': 'add_user_last_login',
            'check': "SELECT * FROM pragma_table_info('user') WHERE name='last_login'",
            'migrate': "ALTER TABLE user ADD COLUMN last_login DATETIME"
        },
        {
            'name': 'add_user_failed_attempts',
            'check': "SELECT * FROM pragma_table_info('user') WHERE name='failed_attempts'",
            'migrate': "ALTER TABLE user ADD COLUMN failed_attempts INTEGER DEFAULT 0"
        },
        {
            'name': 'add_user_locked_until',
            'check': "SELECT * FROM pragma_table_info('user') WHERE name='locked_until'",
            'migrate': "ALTER TABLE user ADD COLUMN locked_until DATETIME"
        },
        {
            'name': 'add_user_created_at',
            'check': "SELECT * FROM pragma_table_info('user') WHERE name='created_at'",
            'migrate': "ALTER TABLE user ADD COLUMN created_at DATETIME"
        },
```

- [ ] **Step 2: Add migrations for FeedBack model new columns**

Add to the same `migrations` list:

```python
        {
            'name': 'add_feedback_resolved',
            'check': "SELECT * FROM pragma_table_info('feed_back') WHERE name='resolved'",
            'migrate': "ALTER TABLE feed_back ADD COLUMN resolved BOOLEAN DEFAULT 0"
        },
        {
            'name': 'add_feedback_admin_notes',
            'check': "SELECT * FROM pragma_table_info('feed_back') WHERE name='admin_notes'",
            'migrate': "ALTER TABLE feed_back ADD COLUMN admin_notes TEXT"
        },
        {
            'name': 'add_feedback_serial_number',
            'check': "SELECT * FROM pragma_table_info('feed_back') WHERE name='serial_number'",
            'migrate': "ALTER TABLE feed_back ADD COLUMN serial_number VARCHAR(100)"
        },
        {
            'name': 'add_feedback_first_response_date',
            'check': "SELECT * FROM pragma_table_info('feed_back') WHERE name='first_response_date'",
            'migrate': "ALTER TABLE feed_back ADD COLUMN first_response_date DATETIME"
        },
        {
            'name': 'add_feedback_resolved_date',
            'check': "SELECT * FROM pragma_table_info('feed_back') WHERE name='resolved_date'",
            'migrate': "ALTER TABLE feed_back ADD COLUMN resolved_date DATETIME"
        },
        {
            'name': 'add_feedback_resolution_time_hours',
            'check': "SELECT * FROM pragma_table_info('feed_back') WHERE name='resolution_time_hours'",
            'migrate': "ALTER TABLE feed_back ADD COLUMN resolution_time_hours INTEGER"
        },
```

- [ ] **Step 3: Update model imports in create_database()**

In `xissite/__init__.py`, update the model import line at line 187:

```python
    from .models import (Customer, Purchase_info, User, FeedBack,
                         LoginAttempt, SiteVisit, BannedIP, GeoIPCache,
                         AdminAuditLog)
```

- [ ] **Step 4: Run smoke tests to verify migrations don't break app startup**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add xissite/__init__.py
git commit -m "Add database migrations for User/FeedBack new columns and new security models"
```

---

### Task 4: Register Admin API Blueprint

The `admin_api.py` file exists but is not connected to the app.

**Files:**
- Modify: `xissite/__init__.py:171-181` (blueprint registration section)
- Create: `tests/test_admin_api.py`

- [ ] **Step 1: Write test for admin API health endpoint**

Create `tests/test_admin_api.py`:

```python
def test_admin_api_health(client):
    """Admin API health endpoint returns 200 without auth."""
    response = client.get('/api/admin/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'ok'


def test_admin_api_requires_auth(client):
    """Admin API endpoints return 401 without Bearer token."""
    response = client.get('/api/admin/stats')
    assert response.status_code in (401, 503)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_admin_api.py -v`
Expected: FAIL (404, blueprint not registered)

- [ ] **Step 3: Register admin_api blueprint in __init__.py**

In `xissite/__init__.py`, add after the existing blueprint imports (after line 177):

```python
    from .admin_api import admin_api
```

Add after the existing blueprint registrations (after line 181):

```python
    app.register_blueprint(admin_api)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_admin_api.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add xissite/__init__.py tests/test_admin_api.py
git commit -m "Register admin API blueprint and add health endpoint test"
```

---

### Task 5: Remove Investor Role

Strip all investor-facing code: decorator, route, login flow branching, template, env-var references.

**Files:**
- Modify: `xissite/auth.py:70-81` (investor_required decorator), `150-171` (investor login branch), `195-204` (investor_portal route)
- Modify: `xissite/admin_api.py:167-168, 195` (user_type validation)
- Modify: `xissite/__init__.py:25-27` (docstring)
- Delete: `xissite/templates/investor.html`
- Create: `tests/test_investor_removal.py`

- [ ] **Step 1: Write tests confirming investor code is gone**

Create `tests/test_investor_removal.py`:

```python
def test_investor_route_removed(client):
    """The /investor route should no longer exist."""
    response = client.get('/investor')
    assert response.status_code == 404


def test_investor_login_rejected(client):
    """No investor credential checking in login flow."""
    import os
    # Even if investor env vars exist, they should not be checked
    os.environ['INVESTOR_USERNAME_HASH'] = 'dummy'
    os.environ['INVESTOR_PASSWORD_HASH'] = 'dummy'

    response = client.post('/login', data={
        'username': 'investor_user',
        'password': 'investor_pass',
    })
    # Should get invalid credentials, not a redirect to /investor
    assert b'investor' not in response.data.lower() or response.status_code != 302

    os.environ.pop('INVESTOR_USERNAME_HASH', None)
    os.environ.pop('INVESTOR_PASSWORD_HASH', None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_investor_removal.py -v`
Expected: At least one FAIL (investor route still exists)

- [ ] **Step 3: Remove investor_required decorator from auth.py**

Delete lines 70-81 in `xissite/auth.py` (the entire `investor_required` function).

- [ ] **Step 4: Remove investor_portal route from auth.py**

Delete lines 191-204 in `xissite/auth.py` (the `# INVESTOR PORTAL` section with the `investor_portal` function).

- [ ] **Step 5: Remove investor credential checking from login route**

In `xissite/auth.py`, remove the investor env-var fetching (lines 109-110):

```python
    investor_username_hash = os.environ.get('INVESTOR_USERNAME_HASH')
    investor_password_hash = os.environ.get('INVESTOR_PASSWORD_HASH')
```

Remove the entire investor login branch (lines 150-171):

```python
        # Check INVESTOR credentials if admin didn't match
        if investor_username_hash and investor_password_hash:
            investor_username_valid = check_password_hash(investor_username_hash, username)
            investor_password_valid = check_password_hash(investor_password_hash, password)

            if investor_username_valid and investor_password_valid:
                # Check if investor user exists, create if not
                investor_user = User.query.filter_by(user_type='investor').first()
                if not investor_user:
                    investor_user = User(
                        email=investor_username_hash,
                        password=investor_password_hash,
                        user_type='investor'
                    )
                    db.session.add(investor_user)
                    db.session.commit()
                    print("[SETUP] Investor user created in database")

                login_user(investor_user, remember=True)
                session['user_type'] = 'investor'
                print(f"[AUTH] Successful INVESTOR login")
                return redirect(url_for('auth.investor_portal'))
```

- [ ] **Step 6: Delete investor.html template**

Delete: `xissite/templates/investor.html`

- [ ] **Step 7: Update admin API user_type validation**

In `xissite/admin_api.py`, change line 167:
```python
    if user_type not in ('admin', 'employee'):
```

Change line 168:
```python
        return jsonify(error='user_type must be admin or employee'), 400
```

Change line 195:
```python
    if 'user_type' in data and data['user_type'] in ('admin', 'employee'):
```

- [ ] **Step 8: Update __init__.py docstring**

In `xissite/__init__.py`, remove lines 25-27:
```
Optional (for investor portal):
- INVESTOR_USERNAME_HASH: Hashed investor username
- INVESTOR_PASSWORD_HASH: Hashed investor password
```

- [ ] **Step 9: Run tests**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 10: Commit**

```bash
git add -A xissite/auth.py xissite/admin_api.py xissite/__init__.py xissite/templates/investor.html tests/test_investor_removal.py
git commit -m "Remove investor role: decorator, route, template, login branching, env-var refs"
```

---

### Task 6: Rewrite Login Route for DB-Backed Auth

Replace env-var credential checking with database User lookup. Add bootstrap admin logic.

**Files:**
- Modify: `xissite/auth.py:88-177` (login route)
- Modify: `xissite/__init__.py:219-237` (create_database function)
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write tests for DB-backed login**

Create `tests/test_auth.py`:

```python
from werkzeug.security import generate_password_hash


def _create_admin(db):
    """Helper: create an admin user in the database."""
    from xissite.models import User
    user = User(
        email='admin',
        password=generate_password_hash('correctpassword1'),
        user_type='admin',
        status='active',
        display_name='Admin',
    )
    db.session.add(user)
    db.session.commit()
    return user


def _create_employee(db):
    """Helper: create an employee user in the database."""
    from xissite.models import User
    user = User(
        email='patrick',
        password=generate_password_hash('patrickpass11'),
        user_type='employee',
        status='active',
        display_name='Patrick T.',
    )
    db.session.add(user)
    db.session.commit()
    return user


def test_login_page_loads(client):
    """GET /login returns 200 with login form."""
    response = client.get('/login')
    assert response.status_code == 200
    assert b'login' in response.data.lower()


def test_login_valid_admin(client, db):
    """Valid admin credentials redirect to /viewdb."""
    _create_admin(db)
    response = client.post('/login', data={
        'username': 'admin',
        'password': 'correctpassword1',
    }, follow_redirects=False)
    assert response.status_code == 302
    assert '/viewdb' in response.headers['Location']


def test_login_valid_employee(client, db):
    """Valid employee credentials redirect to /ops (or home for now)."""
    _create_employee(db)
    response = client.post('/login', data={
        'username': 'patrick',
        'password': 'patrickpass11',
    }, follow_redirects=False)
    assert response.status_code == 302


def test_login_invalid_password(client, db):
    """Wrong password shows error, doesn't redirect."""
    _create_admin(db)
    response = client.post('/login', data={
        'username': 'admin',
        'password': 'wrongpassword',
    }, follow_redirects=True)
    assert b'Invalid credentials' in response.data


def test_login_nonexistent_user(client, db):
    """Username that doesn't exist shows generic error."""
    response = client.post('/login', data={
        'username': 'nobody',
        'password': 'somepassword',
    }, follow_redirects=True)
    assert b'Invalid credentials' in response.data


def test_login_suspended_user(client, db):
    """Suspended users cannot log in."""
    user = _create_admin(db)
    user.status = 'suspended'
    db.session.commit()

    response = client.post('/login', data={
        'username': 'admin',
        'password': 'correctpassword1',
    }, follow_redirects=True)
    assert b'suspended' in response.data.lower() or b'Invalid' in response.data


def test_login_records_attempt(client, db):
    """Login attempts are logged to LoginAttempt table."""
    from xissite.models import LoginAttempt
    _create_admin(db)

    client.post('/login', data={
        'username': 'admin',
        'password': 'wrongpassword',
    })

    attempts = LoginAttempt.query.all()
    assert len(attempts) == 1
    assert attempts[0].success is False
    assert attempts[0].username_attempted == 'admin'


def test_login_updates_last_login(client, db):
    """Successful login updates user.last_login."""
    from xissite.models import User
    _create_admin(db)

    client.post('/login', data={
        'username': 'admin',
        'password': 'correctpassword1',
    })

    user = User.query.filter_by(email='admin').first()
    assert user.last_login is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_auth.py -v`
Expected: FAIL (login still uses env vars)

- [ ] **Step 3: Rewrite the login route in auth.py**

Replace the entire login function (from `@auth.route('/login'...` through `return render_template('loginpage.html', form=form)`) with:

```python
@auth.route('/login', methods=['GET', 'POST'])
def login():
    """
    Login page for Admin and Employee users.

    GET: Displays login form
    POST: Validates credentials against User table in database
    """
    form = LoginForm()

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()

        # Look up user by email/username in database
        user = User.query.filter_by(email=username).first()

        # Determine login result
        success = False
        failure_reason = None

        if user is None:
            failure_reason = 'unknown_user'
        elif user.status == 'suspended':
            failure_reason = 'account_suspended'
            flash('Account suspended. Contact your administrator.', 'error')
        elif user.status == 'deleted':
            failure_reason = 'unknown_user'
        elif user.locked_until and user.locked_until > datetime.now(timezone.utc):
            remaining = int((user.locked_until - datetime.now(timezone.utc)).total_seconds() / 60) + 1
            failure_reason = 'account_locked'
            flash(f'Account temporarily locked. Try again in {remaining} minutes.', 'error')
        elif not check_password_hash(user.password, password):
            failure_reason = 'invalid_password'
        else:
            success = True

        # Log the attempt
        from .models import LoginAttempt
        attempt = LoginAttempt(
            ip_address=client_ip,
            user_agent=request.headers.get('User-Agent', '')[:500],
            username_attempted=username,
            success=success,
            failure_reason=failure_reason,
            user_type_matched=user.user_type if user and success else None,
        )
        db.session.add(attempt)

        if success:
            user.failed_attempts = 0
            user.locked_until = None
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()
            login_user(user, remember=True)
            print(f"[AUTH] Successful {user.user_type.upper()} login: {username}")

            if user.user_type == 'admin':
                return redirect(url_for('auth.viewdatabase'))
            else:
                return redirect(url_for('views.home'))
        else:
            # Handle failed attempt
            if user and failure_reason == 'invalid_password':
                user.failed_attempts = (user.failed_attempts or 0) + 1
                if user.failed_attempts >= 10:
                    user.locked_until = datetime.now(timezone.utc) + timedelta(hours=1)
                elif user.failed_attempts >= 5:
                    user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
            db.session.commit()

            if not failure_reason or failure_reason in ('unknown_user', 'invalid_password'):
                flash('Invalid credentials', 'error')
            print(f"[AUTH] Failed login attempt: {username} ({failure_reason})")

    return render_template('loginpage.html', form=form)
```

- [ ] **Step 4: Add required imports to auth.py**

At the top of `xissite/auth.py`, add to existing imports:

```python
from datetime import datetime, timedelta, timezone
```

Remove the `csrf = CSRFProtect()` line (line 31) since CSRF is handled by the app-level CSRFProtect in `__init__.py`. Also remove the `csrf.protect()` call from the login function (it was on old line 103) -- Flask-WTF handles this through the form.

- [ ] **Step 5: Remove the old GET-based admin auto-creation**

The old code (lines 119-125) auto-created an admin user from env-var hashes on first GET. This is replaced by the bootstrap logic below. Remove:

```python
    # On first visit, ensure admin user exists in database
    if request.method == 'GET':
        admin_check = db.session.query(User).first()
        if admin_check is None:
            new_admin = User(email=admin_username_hash, password=admin_password_hash, user_type='admin')
            db.session.add(new_admin)
            db.session.commit()
            print("[SETUP] Admin user created in database")
```

- [ ] **Step 6: Add bootstrap admin to create_database()**

In `xissite/__init__.py`, add bootstrap logic at the end of `create_database()`, after `run_migrations()`:

```python
        # Clean up old-style users (env-var hash artifacts)
        old_users = User.query.filter(
            User.email.like('scrypt:%') | User.email.like('pbkdf2:%')
        ).all()
        for old_user in old_users:
            db.session.delete(old_user)
        if old_users:
            db.session.commit()
            print(f'[MIGRATION] Removed {len(old_users)} old-style user(s) with hash artifacts')

        # Bootstrap admin account on first run
        if User.query.count() == 0:
            bootstrap_email = os.environ.get('ADMIN_BOOTSTRAP_EMAIL', 'admin')
            bootstrap_password = os.environ.get('ADMIN_BOOTSTRAP_PASSWORD')
            if bootstrap_password:
                from werkzeug.security import generate_password_hash
                admin = User(
                    email=bootstrap_email,
                    password=generate_password_hash(bootstrap_password),
                    user_type='admin',
                    status='active',
                    display_name='Admin',
                )
                db.session.add(admin)
                db.session.commit()
                print(f'[SETUP] Bootstrap admin created (username: {bootstrap_email}). Change password via TullOps.')
            else:
                print('[WARNING] No users exist and ADMIN_BOOTSTRAP_PASSWORD not set. Create users via admin API.')
```

- [ ] **Step 7: Update the admin_required decorator to use DB user_type**

In `xissite/auth.py`, replace the `admin_required` function:

```python
def admin_required(f):
    """Decorator to require admin access."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.user_type != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function
```

- [ ] **Step 8: Add employee_required decorator**

Add after admin_required in `xissite/auth.py`:

```python
def employee_required(f):
    """Decorator to require at least employee access (admin also passes)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.user_type not in ('admin', 'employee'):
            flash('Access denied.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function
```

- [ ] **Step 9: Remove session['user_type'] from logout**

In `xissite/auth.py`, update the logout function to remove the session pop:

```python
@auth.route('/logout')
@login_required
def logout():
    """Log out the current user and redirect to login page."""
    print(f"[AUTH] {current_user.user_type.upper()} user logged out")
    logout_user()
    return redirect(url_for('auth.login'))
```

- [ ] **Step 10: Run auth tests**

Run: `python -m pytest tests/test_auth.py -v`
Expected: All tests PASS

- [ ] **Step 11: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 12: Commit**

```bash
git add xissite/auth.py xissite/__init__.py tests/test_auth.py
git commit -m "Rewrite login for DB-backed auth, add bootstrap admin, remove env-var credentials"
```

---

### Task 7: Session Hardening

Configure secure cookie flags and session timeouts.

**Files:**
- Modify: `xissite/__init__.py:136-158` (configuration section)

- [ ] **Step 1: Add session security config to create_app()**

In `xissite/__init__.py`, add after the CSRF config line (`app.config['WTF_CSRF_CHECK_DEFAULT'] = False`):

```python
    # Session security
    from datetime import timedelta
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
    app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=7)
    app.config['REMEMBER_COOKIE_HTTPONLY'] = True
    app.config['REMEMBER_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    # Secure cookies only in production (HTTPS)
    if not is_development():
        app.config['REMEMBER_COOKIE_SECURE'] = True
        app.config['SESSION_COOKIE_SECURE'] = True
```

- [ ] **Step 2: Run tests to verify nothing broke**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add xissite/__init__.py
git commit -m "Add session hardening: cookie security flags, 8-hour sessions, 7-day remember"
```

---

### Task 8: Login Rate Limiting (Per-IP)

Add per-IP rate limiting and banned IP checking to the login route.

**Files:**
- Modify: `xissite/auth.py` (login route, add IP checks at top)
- Create: `tests/test_rate_limiting.py`

- [ ] **Step 1: Write rate limiting tests**

Create `tests/test_rate_limiting.py`:

```python
from werkzeug.security import generate_password_hash


def _create_admin(db):
    from xissite.models import User
    user = User(
        email='admin',
        password=generate_password_hash('correctpassword1'),
        user_type='admin',
        status='active',
    )
    db.session.add(user)
    db.session.commit()
    return user


def test_banned_ip_rejected(client, db):
    """Banned IPs are rejected before credential check."""
    from xissite.models import BannedIP
    _create_admin(db)

    ban = BannedIP(
        ip_address='127.0.0.1',
        reason='test ban',
        banned_by='test',
        active=True,
    )
    db.session.add(ban)
    db.session.commit()

    response = client.post('/login', data={
        'username': 'admin',
        'password': 'correctpassword1',
    }, follow_redirects=True)
    # Should be rejected even with correct credentials
    assert b'blocked' in response.data.lower() or b'banned' in response.data.lower()


def test_account_locks_after_5_failures(client, db):
    """Account locks after 5 consecutive failed attempts."""
    from xissite.models import User
    _create_admin(db)

    for _ in range(5):
        client.post('/login', data={
            'username': 'admin',
            'password': 'wrongpassword',
        })

    user = User.query.filter_by(email='admin').first()
    assert user.failed_attempts >= 5
    assert user.locked_until is not None


def test_successful_login_resets_lockout(client, db):
    """Successful login resets failed_attempts and locked_until."""
    from xissite.models import User
    user = _create_admin(db)
    user.failed_attempts = 3
    db.session.commit()

    client.post('/login', data={
        'username': 'admin',
        'password': 'correctpassword1',
    })

    user = User.query.filter_by(email='admin').first()
    assert user.failed_attempts == 0
    assert user.locked_until is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_rate_limiting.py -v`
Expected: At least `test_banned_ip_rejected` FAIL

- [ ] **Step 3: Add banned IP check and per-IP rate limiting to login route**

In `xissite/auth.py`, add at the very beginning of `if request.method == 'POST':` block, before the username fetch:

```python
        # Check if IP is banned
        from .models import BannedIP, LoginAttempt as LA
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()

        active_ban = BannedIP.query.filter_by(
            ip_address=client_ip, active=True
        ).first()
        if active_ban:
            # Check if ban has expired
            if active_ban.expires_at and active_ban.expires_at < datetime.now(timezone.utc):
                active_ban.active = False
                db.session.commit()
            else:
                flash('Access blocked. Contact your administrator.', 'error')
                return render_template('loginpage.html', form=form)

        # Per-IP rate limiting: reject after 10 failed attempts in 1 hour
        hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        ip_failures = LA.query.filter(
            LA.ip_address == client_ip,
            LA.success == False,
            LA.timestamp >= hour_ago,
        ).count()

        auto_ban_threshold = int(os.environ.get('AUTO_BAN_THRESHOLD', '20'))
        if ip_failures >= auto_ban_threshold:
            # Auto-ban this IP
            ban_hours = int(os.environ.get('AUTO_BAN_WINDOW_HOURS', '1'))
            auto_ban = BannedIP(
                ip_address=client_ip,
                reason=f'Auto-banned: {ip_failures} failed attempts in 1 hour',
                banned_by='auto',
                active=True,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=ban_hours),
            )
            db.session.add(auto_ban)
            db.session.commit()
            flash('Access blocked. Contact your administrator.', 'error')
            return render_template('loginpage.html', form=form)

        if ip_failures >= 10:
            flash('Too many failed attempts. Try again later.', 'error')
            return render_template('loginpage.html', form=form)
```

Remove the duplicate `client_ip` lines that were already in the login function body (from Task 6) since we now compute it earlier. Also add `import os` back to auth.py imports (needed for env var reads).

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_rate_limiting.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add xissite/auth.py tests/test_rate_limiting.py
git commit -m "Add login rate limiting: banned IP check, per-account lockout after 5/10 failures"
```

---

### Task 9: Admin API Alignment

Ensure the activate endpoint resets lockout, and the password policy is enforced.

**Files:**
- Modify: `xissite/admin_api.py:231-238` (activate_user), `156-184` (create_user)
- Create: `tests/test_admin_api_auth.py`

- [ ] **Step 1: Write tests for admin unlock and password policy**

Create `tests/test_admin_api_auth.py`:

```python
import os
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash


def _auth_header():
    """Return Bearer token header for admin API."""
    api_key = os.environ.get('ADMIN_API_KEY', 'test-api-key')
    os.environ['ADMIN_API_KEY'] = api_key
    return {'Authorization': f'Bearer {api_key}'}


def test_activate_resets_lockout(client, db):
    """POST /api/admin/users/<uid>/activate resets failed_attempts and locked_until."""
    from xissite.models import User

    user = User(
        email='locked_user',
        password=generate_password_hash('testpassword1'),
        user_type='employee',
        status='suspended',
        failed_attempts=10,
        locked_until=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.session.add(user)
    db.session.commit()

    response = client.post(
        f'/api/admin/users/{user.id}/activate',
        headers=_auth_header(),
    )
    assert response.status_code == 200

    refreshed = User.query.get(user.id)
    assert refreshed.status == 'active'
    assert refreshed.failed_attempts == 0
    assert refreshed.locked_until is None


def test_create_user_password_too_short(client, db):
    """Creating a user with password < 10 chars is rejected."""
    response = client.post(
        '/api/admin/users',
        headers=_auth_header(),
        json={
            'email': 'newuser@tull.com',
            'password': 'short',
            'user_type': 'employee',
        },
    )
    assert response.status_code == 400
    assert 'password' in response.get_json().get('error', '').lower()


def test_create_user_valid(client, db):
    """Creating a user with valid password succeeds."""
    response = client.post(
        '/api/admin/users',
        headers=_auth_header(),
        json={
            'email': 'newuser@tull.com',
            'password': 'validpassword123',
            'user_type': 'employee',
        },
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data['email'] == 'newuser@tull.com'
    assert data['user_type'] == 'employee'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_admin_api_auth.py -v`
Expected: FAIL (activate doesn't reset lockout, no password length check)

- [ ] **Step 3: Update activate_user to reset lockout**

In `xissite/admin_api.py`, replace the `activate_user` function:

```python
@admin_api.route('/users/<int:uid>/activate', methods=['POST'])
@require_api_key
def activate_user(uid):
    user = User.query.get_or_404(uid)
    user.status = 'active'
    user.failed_attempts = 0
    user.locked_until = None
    db.session.commit()
    _audit('user.activate', 'user', uid)
    return jsonify(user.to_dict())
```

- [ ] **Step 4: Add password length validation to create_user**

In `xissite/admin_api.py`, in the `create_user` function, add after the `if not email or not password:` check:

```python
    if len(password) < 10:
        return jsonify(error='Password must be at least 10 characters'), 400
```

- [ ] **Step 5: Add password length validation to update_user**

In `xissite/admin_api.py`, in the `update_user` function, change the password update block:

```python
    if 'password' in data and data['password']:
        if len(data['password']) < 10:
            return jsonify(error='Password must be at least 10 characters'), 400
        user.password = generate_password_hash(data['password'])
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_admin_api_auth.py -v`
Expected: All 3 tests PASS

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add xissite/admin_api.py tests/test_admin_api_auth.py
git commit -m "Admin API: activate resets lockout, enforce 10-char password minimum"
```

---

### Task 10: Clean Up and Final Verification

Remove unused env-var references, update docstrings, run full test suite.

**Files:**
- Modify: `xissite/auth.py` (clean up unused imports)
- Modify: `xissite/__init__.py` (update module docstring)

- [ ] **Step 1: Clean up auth.py imports**

In `xissite/auth.py`, ensure the imports section looks like:

```python
from flask import Blueprint, redirect, url_for, render_template, request, flash
from sqlalchemy.sql import func
from datetime import datetime, timedelta, timezone
import os
from werkzeug.security import check_password_hash
from flask_login import login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField
from wtforms.validators import DataRequired, Length
from functools import wraps

from . import db
from .models import Customer, FeedBack, Purchase_info, User
```

Remove: `from flask_wtf.csrf import CSRFProtect`, and the `csrf = CSRFProtect()` line. The `session` import from flask is no longer needed (role comes from `current_user.user_type`). Keep `import os` (needed for AUTO_BAN_THRESHOLD env var in rate limiting).

- [ ] **Step 2: Update __init__.py module docstring**

Replace the docstring at the top of `xissite/__init__.py` (lines 2-28) with:

```python
"""
Tull Hydroponics Flask Application Factory
==========================================

This module initializes the Flask application with:
- SQLAlchemy database connection
- CSRF protection
- Flask-Login for authentication
- Blueprint registration for routes

AUTOMATIC ENVIRONMENT DETECTION:
    The app automatically detects whether it's running locally or on Google Cloud
    and configures itself appropriately. No code changes needed for deployment.

Environment Variables Required:
- FLASK_SECRET_KEY: Secret key for session management
- ADMIN_BOOTSTRAP_EMAIL: Bootstrap admin username (first-run only, default: 'admin')
- ADMIN_BOOTSTRAP_PASSWORD: Bootstrap admin password (first-run only)
- STRIPE_SECRET_KEY: Stripe API secret key
- STRIPE_PUBLISHABLE_KEY: Stripe publishable key
- STRIPE_WEBHOOK_SECRET: Stripe webhook signing secret
- HP_PRICE_ID: Stripe Price ID for the product
- MAIL_KEY: Mailgun API key for order confirmations
- ADMIN_API_KEY: Bearer token for admin REST API (used by TullOps)
"""
```

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Manual smoke test**

Run: `cd C:/Users/adoni/Desktop/TullSite && python main.py`

Verify:
1. App starts without errors
2. Bootstrap admin message prints if DB is fresh
3. `/login` page loads
4. `/api/admin/health` returns `{"status": "ok"}`
5. Ctrl+C to stop

- [ ] **Step 5: Commit**

```bash
git add xissite/auth.py xissite/__init__.py
git commit -m "Clean up imports and docstrings after auth overhaul"
```

- [ ] **Step 6: Final commit with all remaining changes**

Check for any unstaged files (the previously modified models.py, views.py, contact.html from git status):

```bash
git status
git add xissite/models.py
git commit -m "Stage models.py working copy changes (submitter_ip field)"
```
