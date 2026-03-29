# TullSite Auth System Security Overhaul

**Date:** 2026-03-29
**Status:** Design review
**Scope:** Migrate from env-var credentials to database-backed auth, harden login security, remove investor role, prepare for TullOps-driven employee portal

---

## Context

TullSite (tullhydro.com) is evolving from a product website with a basic admin panel into the **internet-facing operations layer for TullOps**. TullOps runs on a local PC and cannot be reached outside the LAN. TullSite bridges that gap -- TullOps pushes operational content (kanban boards, deployment checklists, diagnostic tools) to TullSite via the admin API, and employees access it from the field.

The current login system uses hardcoded env-var credential hashes and supports only two roles (admin, investor). It needs to support multiple individual employee accounts managed remotely by TullOps, with proper session security, rate limiting, and eventual 2FA.

### Key Architectural Principle

**TullOps is the authority. TullSite is the delivery channel.**

- TullOps creates and manages all user accounts via `POST/PUT/DELETE /api/admin/users`
- TullOps pushes operational content to TullSite for employees to consume
- TullSite authenticates employees and serves what TullOps has assigned to them
- Admin can view all content served to any employee, and control what each employee sees
- TullSite never generates operational content on its own

---

## 1. Remove Investor Role

Strip all investor-facing capabilities:

- Remove `@investor_required` decorator from `auth.py`
- Remove `/investor` route and `investor.html` template
- Remove `INVESTOR_USERNAME_HASH` / `INVESTOR_PASSWORD_HASH` env-var checks from login flow
- Remove investor credential branching from `POST /login`
- Clean up any existing investor User records during migration
- Remove investor references from admin API user creation validation (change allowed types from `('admin', 'investor')` to `('admin', 'employee')`)

**Roles after migration:** `admin` and `employee` only.

---

## 2. Database-Backed Authentication

### 2a. Migrate Login Validation

**Current flow** (`auth.py` login route):
```
POST /login
  -> get ADMIN_USERNAME_HASH from env
  -> check_password_hash(env_hash, form_username)
  -> check_password_hash(env_hash, form_password)
```

**New flow:**
```
POST /login
  -> check BannedIP table (reject if banned)
  -> User.query.filter_by(email=form_username).first()
  -> check user.locked_until (reject if locked)
  -> check_password_hash(user.password, form_password)
  -> check user.status == 'active'
  -> log attempt to LoginAttempt table
  -> login_user(user) -- Flask-Login handles session
```

The login route validates against the `User` table directly. No env vars involved in credential checking. Role is read from `current_user.user_type` (loaded from DB by Flask-Login's user_loader), not stored separately in the session.

### 2b. Bootstrap Admin (First-Run Only)

One env var remains for initial deployment: `ADMIN_BOOTSTRAP_PASSWORD`.

On first app startup with an empty User table:
1. Create an admin user with email from `ADMIN_BOOTSTRAP_EMAIL` (or default `admin`)
2. Hash the `ADMIN_BOOTSTRAP_PASSWORD` and store in `User.password`
3. Print a console message: `[SETUP] Bootstrap admin created. Change password via TullOps.`
4. This only runs if zero User records exist

After bootstrap, all account management happens through TullOps via the admin API.

### 2c. User Model Updates

Add fields to the `User` model:

```python
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)       # now stores actual username/email
    password = db.Column(db.String(256))                   # werkzeug scrypt hash
    user_type = db.Column(db.String(50), default='employee')  # 'admin' or 'employee'
    status = db.Column(db.String(50), default='active')    # 'active', 'suspended', 'deleted'
    display_name = db.Column(db.String(150))               # e.g. "Patrick T."
    notes = db.Column(db.Text)                             # admin notes
    last_login = db.Column(db.DateTime)                    # last successful login
    failed_attempts = db.Column(db.Integer, default=0)     # consecutive failures
    locked_until = db.Column(db.DateTime)                  # account lockout expiry
    created_at = db.Column(db.DateTime, default=func.now())
```

Migration SQL for existing databases:
- `ALTER TABLE user ADD COLUMN status VARCHAR(50) DEFAULT 'active'`
- `ALTER TABLE user ADD COLUMN display_name VARCHAR(150)`
- `ALTER TABLE user ADD COLUMN notes TEXT`
- `ALTER TABLE user ADD COLUMN last_login DATETIME`
- `ALTER TABLE user ADD COLUMN failed_attempts INTEGER DEFAULT 0`
- `ALTER TABLE user ADD COLUMN locked_until DATETIME`
- `ALTER TABLE user ADD COLUMN created_at DATETIME`

---

## 3. Session Security

### Current state
- `remember=True` with no expiry (sessions live indefinitely)
- No secure cookie flags explicitly set
- `WTF_CSRF_CHECK_DEFAULT = False` (CSRF opt-in per route)

### Changes

Add to `create_app()` configuration:

```python
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=7)
app.config['REMEMBER_COOKIE_SECURE'] = True        # HTTPS only in production
app.config['REMEMBER_COOKIE_HTTPONLY'] = True       # no JS access
app.config['REMEMBER_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True          # HTTPS only in production
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
```

Session lifetime: 8-hour working sessions, 7-day remember-me. Configurable via env vars if needed.

Secure cookie flags should only be enforced when `not is_development()` to avoid breaking local dev (localhost is HTTP).

---

## 4. Login Rate Limiting and Lockout

### Per-Account Lockout

Track `failed_attempts` on the User record:
- Each failed login increments `user.failed_attempts`
- After 5 consecutive failures: lock account for 15 minutes (`user.locked_until = now + 15min`)
- After 10 consecutive failures: lock account for 1 hour
- Successful login resets `failed_attempts` to 0 and clears `locked_until`
- Locked accounts show: "Account temporarily locked. Try again in X minutes."
- Admin can manually unlock any account via `POST /api/admin/users/<uid>/activate` (already exists) -- this resets `failed_attempts` to 0 and clears `locked_until`

### Per-IP Rate Limiting

Use the existing `LoginAttempt` model (already imported in `admin_api.py`):
- Log every login attempt (success/failure, IP, username, timestamp)
- After 10 failed attempts from the same IP in 1 hour: reject with generic error
- After threshold defined by `AUTO_BAN_THRESHOLD` env var: add to `BannedIP` table (model already exists)
- Check `BannedIP` at the top of the login route before processing credentials

### LoginAttempt Logging

Every POST to `/login` creates a record:
```python
attempt = LoginAttempt(
    username=form_username,
    ip_address=request.headers.get('X-Forwarded-For', request.remote_addr),
    user_agent=request.headers.get('User-Agent', ''),
    success=True/False,
    timestamp=datetime.now(timezone.utc)
)
```

This feeds the existing admin API security monitoring endpoints (login heatmap, brute force detection, alerts).

---

## 5. Admin Permissions Model

### Role Definitions

**Admin:**
- Full access to all existing admin routes (`/viewdb`, feedback, customer data)
- Can view any content assigned to any employee
- Content management capabilities (once employee portal features are built)
- Account management via TullOps admin API

**Employee:**
- Sees only what TullOps has pushed/assigned to them
- No access to `/viewdb`, customer data, or feedback (admin-only routes stay admin-only)
- Gets a personalized `/ops` dashboard (future feature, not in this security overhaul scope)
- Account state (active tools, current mode) is controlled by admin via the API

### How Admin Controls Employee Views

This is a **future feature** (not implemented in this security overhaul) but the auth system should be designed to support it:

- TullOps will push "assignments" to employees via the admin API (e.g., deploy mode, checklists, diagnostics)
- Employees see their assignments on their dashboard
- Admin can preview/view any assignment
- The data model for assignments is out of scope here; the auth system just needs the role infrastructure

### Decorator Changes

Replace current decorators:

```python
@admin_required       # existing - keeps working, now checks DB user_type
@employee_required    # new - replaces @investor_required
@login_required       # existing Flask-Login - keeps working
```

The `@admin_required` decorator checks `current_user.user_type == 'admin'` (from DB, not session). Session `user_type` is removed as the source of truth -- the User record is authoritative.

---

## 6. Email 2FA (Phase 2)

This is intentionally separated as a follow-on phase. The core auth migration and hardening should land first, then 2FA layers on top.

### Design (for when implemented)

- On login from unrecognized device, send 6-digit code to user's email
- Code generated via `secrets.token_hex(3)` converted to 6-digit number
- Code stored as hash in DB with 10-minute expiry
- "Remember this device" signed cookie, 30 days
- Uses existing Mailgun integration (`MAIL_KEY` env var)
- Requires `User.email` to store a real, deliverable email address

### Why Phase 2

- The core migration (env vars to DB, rate limiting, session hardening) provides the biggest security uplift
- 2FA adds friction; better to stabilize the auth flow first
- Mailgun email deliverability should be verified before relying on it for auth codes
- Can be enabled per-role (admin first, then employees) for gradual rollout

---

## 7. Password Policy

Enforced at account creation and password change (in admin API endpoints):

- Minimum 10 characters
- No maximum length cap (let password managers do their thing)
- No complexity regex (length is the primary defense per NIST 800-63B)
- Passwords hashed with Werkzeug scrypt (already in place, no change needed)

---

## 8. Migration Plan (High-Level)

### Step 0: Migrate existing admin user
The current DB has an admin user with env-var hashes stored in the email/password fields. This record needs to be updated: set `email` to a real username (e.g. from `ADMIN_BOOTSTRAP_EMAIL`), set a new hashed password, and populate the new columns. This can happen as part of the bootstrap logic -- if an old-style user exists (email looks like a hash), prompt for re-setup.

### Step 1: User model updates + migrations
Add new columns to User model. Run `ALTER TABLE` migrations.

### Step 2: Remove investor role
Delete investor decorator, route, template, env-var checks. Update admin API to accept `('admin', 'employee')`.

### Step 3: Rewrite login route
Validate against DB. Log attempts. Check lockout. Bootstrap admin on first run.

### Step 4: Session hardening
Add cookie security config. Set session/remember timeouts.

### Step 5: Rate limiting on /login
Check banned IPs. Track per-IP failures. Auto-lockout.

### Step 6: Admin API alignment
Ensure user CRUD endpoints match new model (status, display_name, failed_attempts, etc.). TullOps can immediately start managing accounts.

### Step 7 (Phase 2): Email 2FA
Layer on device-based email codes after core auth is stable.

---

## 9. Env Var Changes

### Removed
- `ADMIN_USERNAME_HASH` (no longer used for login validation)
- `ADMIN_PASSWORD_HASH` (no longer used for login validation)
- `INVESTOR_USERNAME_HASH` (investor role removed)
- `INVESTOR_PASSWORD_HASH` (investor role removed)

### Added
- `ADMIN_BOOTSTRAP_EMAIL` (first-run admin email/username, optional, defaults to 'admin')
- `ADMIN_BOOTSTRAP_PASSWORD` (first-run admin password, required on fresh deploy)

### Unchanged
- `FLASK_SECRET_KEY` (session signing)
- `ADMIN_API_KEY` (TullOps API authentication)
- `AUTO_BAN_THRESHOLD` (IP ban threshold)
- `AUTO_BAN_WINDOW_HOURS` (IP ban window)
- `MAIL_KEY` (Mailgun, used later for 2FA)

---

## 10. What This Does NOT Cover

- Employee dashboard UI (kanban, checklists, deployment tools) -- separate feature
- Content assignment model (how TullOps pushes tools to employees) -- separate feature
- Partner/Ecobay deployment (handled via TullOps laptop fork, not TullSite)
- Public-facing site changes (no impact to /, /about, /contact, /sell)
- Stripe/payment flow (no impact)
