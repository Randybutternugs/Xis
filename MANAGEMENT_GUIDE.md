# Tull Hydroponics - Management Guide

This guide covers database management, user administration, deployment, and troubleshooting.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Environment Setup](#environment-setup)
3. [User Management](#user-management)
4. [Database Management](#database-management)
5. [Deployment to Google Cloud](#deployment-to-google-cloud)
6. [Stripe Configuration](#stripe-configuration)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Local Development

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Generate credentials (interactive)
python setup_credentials.py

# 3. Run the server
python main.py

# 4. Open http://localhost:5000
```

### Default Test Credentials (vars.env)

| User Type | Username | Password |
|-----------|----------|----------|
| Admin | admin | admin123 |

---

## Environment Setup

### Local Development (vars.env)

The `vars.env` file is used for local development only. It's automatically loaded when you run `python main.py`.

```bash
# Copy the example file
cp vars.env.example vars.env

# Edit with your values
notepad vars.env  # Windows
nano vars.env     # Linux/Mac
```

### Google Cloud (app.yaml)

For production, all environment variables are set in `app.yaml`. The app automatically detects when it's running on Google Cloud.

**Important:** Never commit `vars.env` to version control. It's already in `.gitignore`.

### Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `FLASK_SECRET_KEY` | Yes | Random string for session security |
| `ADMIN_BOOTSTRAP_EMAIL` | Yes | Initial admin username/email (first-run only) |
| `ADMIN_BOOTSTRAP_PASSWORD` | Yes | Initial admin password (first-run only) |
| `ADMIN_BOOTSTRAP_DISPLAY_NAME` | No | Initial admin display name |
| `ADMIN_API_KEY` | Yes | API key for TullOps remote management |
| `AUTO_BAN_THRESHOLD` | No | IP auto-ban after N failures (default: 20) |
| `AUTO_BAN_WINDOW_HOURS` | No | Auto-ban duration in hours (default: 1) |
| `STRIPE_SECRET_KEY` | Yes | Stripe API secret key |
| `STRIPE_PUBLISHABLE_KEY` | Yes | Stripe API publishable key |
| `STRIPE_WEBHOOK_SECRET` | Yes | Stripe webhook signing secret |
| `HP_PRICE_ID` | Yes | Stripe Price ID for your product |
| `POSTMARK_SERVER_TOKEN` | Yes | Postmark API key for transactional emails |
| `POSTMARK_SENDER_EMAIL` | Yes | Verified Postmark sender; email is skipped when either Postmark value is unset |
| `MAIN_DOMAIN` | Yes | Your domain (e.g., https://tullhydro.com) |
| `DATABASE_URL` | No | SQLAlchemy URL (e.g. Cloud SQL); when unset the app uses SQLite |
| `BRUTE_FORCE_THRESHOLD` / `SUSPICIOUS_THRESHOLD` | No | Security-alert thresholds (default: 5 per hour, 3 per day) |

---

## User Management

### Understanding User Types

| User Type | Access | Destination After Login |
|-----------|--------|------------------------|
| `admin` | Customer database, purchases, feedback, all admin routes | `/admin` |
| `employee` | Operational tools pushed by TullOps | `/ops` |

### Managing Users

All user accounts are managed via the TullOps admin API. The bootstrap admin is created automatically on first run from environment variables.

**Create user via API:**
```bash
curl -X POST http://tullhydro.com/api/admin/users \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "min10chars!", "user_type": "employee", "display_name": "Name"}'
```

**Update user:**
```bash
curl -X PUT http://tullhydro.com/api/admin/users/1 \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"status": "active", "display_name": "New Name"}'
```

**Suspend/activate user:**
```bash
curl -X POST http://tullhydro.com/api/admin/users/1/suspend -H "Authorization: Bearer YOUR_API_KEY"
curl -X POST http://tullhydro.com/api/admin/users/1/activate -H "Authorization: Bearer YOUR_API_KEY"
```

### Password Policy

- Minimum 10 characters
- No complexity regex (length is the primary defense per NIST 800-63B)
- Passwords hashed with Werkzeug scrypt

### Account Lockout

- 5 consecutive failed logins: 15-minute lockout
- 10 consecutive failed logins: 1-hour lockout
- Admin can unlock via `POST /api/admin/users/<id>/activate`

---

## Database Management

### Database Location

| Environment | Location | Persistence |
|-------------|----------|-------------|
| Local | `./tullhydro.db` | Permanent |
| Google Cloud (SQLite) | `/tmp/tullhydro.db` | Ephemeral (resets on deploy) |
| Google Cloud (Cloud SQL) | Cloud SQL instance | Permanent |

### Viewing the Database

#### Admin dashboard and panel

Log in as an admin at `/login` and you land on `/admin`: users, login attempts, customers, orders, feedback, visitors and security alerts on one page. The same data is available in the local admin panel (`admin_panel/`, see its README) and through the `/api/admin` API.

#### Command line (local)

```bash
python -m xissite.manage_db status      # Row counts for every table
python -m xissite.manage_db customers
python -m xissite.manage_db purchases
python -m xissite.manage_db feedback
python -m xissite.manage_db users
python -m xissite.manage_db export --out ./export   # CSV files
```

The CLI runs on the app's models, so it follows the current schema and whatever database `DATABASE_URL` (or the local SQLite file) points at.

#### DB Browser for SQLite

Open `tullhydro.db` in [DB Browser for SQLite](https://sqlitebrowser.org/) to browse the local file directly.

### Database Schema

Nine tables. Only `purchase_info.customer_id` is a declared foreign key; the security and analytics tables relate by IP address value. All `DATETIME` columns are written as UTC and come back from SQLite without a timezone (see `xissite/timeutil.py`).

```
customer                          purchase_info
├── id                            ├── id                 (used as the order number)
├── email                         ├── product_name
├── name                          ├── city, state, country, line1, line2, postal_code
└── creation_date                 ├── pay_status         ('paid', 'unpaid', ...) from Stripe
                                  ├── purchase_date
                                  └── customer_id  -> customer.id

feed_back                         user
├── id                (TULL-nnnnn)├── id
├── feedbackmail                  ├── email              (login name, unique)
├── feedbacktype                  ├── password           (scrypt hash)
├── feedbackorderid               ├── user_type          ('admin' | 'employee')
├── feedbackfullfield             ├── status             ('active' | 'suspended' | 'deleted')
├── date                          ├── display_name, notes
├── submitter_ip                  ├── last_login
├── resolved, admin_notes         ├── failed_attempts, locked_until
├── serial_number                 └── created_at
├── first_response_date
├── resolved_date
└── resolution_time_hours

login_attempt                     banned_ip
├── id                            ├── id
├── ip_address                    ├── ip_address
├── user_agent                    ├── reason
├── username_attempted            ├── banned_by          ('auto' | 'admin')
├── success, failure_reason       ├── active
├── user_type_matched             ├── created_date
└── timestamp                     └── expires_at         (null = permanent)

site_visit                        geo_ip_cache                 admin_audit_log
├── id                            ├── id                       ├── id
├── ip_address                    ├── ip_address (unique)      ├── action        (e.g. user.create)
├── path, referrer                ├── country, region, city    ├── target_type, target_id
├── user_agent                    ├── isp                      ├── details       (JSON)
└── timestamp                     └── cached_at                ├── admin_ip
                                                               └── timestamp
```

### Backing Up the Database (Local)

```bash
python -m xissite.manage_db backup      # writes tullhydro_backup_<timestamp>.db next to the file
```

Backup and reset only work when the app is using a SQLite file. For Cloud SQL, use Google's backup tooling.

### Resetting the Database (Local)

```bash
python -m xissite.manage_db reset       # takes a backup, asks for confirmation, deletes the file
python main.py                          # recreates the tables and the bootstrap admin
```

### Exporting Data to CSV

```bash
python -m xissite.manage_db export --out ./export
```

Writes `customers.csv`, `purchases.csv` and `feedback.csv` with the current column names. The admin API's `/api/admin/export/<table>` returns the same tables (plus `logins`) with spreadsheet-formula characters neutralised.

### Database Migrations

On every start, `create_database()` runs `db.create_all()` and then a list of idempotent "add column if missing" migrations in `xissite/__init__.py` (sixteen today, covering the `user`, `feed_back` and `purchase_info` columns added since the first schema). A fresh database gets the full schema from the models; an older file gets the missing columns added. No action is needed on upgrade.

### Persistence on App Engine

With SQLite in `/tmp`, **every deploy and every instance restart erases the database**: users (except the bootstrap admin, which is recreated from environment variables), customers, purchases, feedback and all login and visitor history. Until the site moves to Cloud SQL, treat App Engine data as disposable and export anything you need to keep.

---

## Deployment to Google Cloud

### Prerequisites

1. [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed
2. A Google Cloud project with billing enabled
3. App Engine enabled for your project

### First-Time Setup

```bash
# Login to Google Cloud
gcloud auth login

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable App Engine
gcloud app create --region=us-central1
```

### Deployment Steps

1. **Update app.yaml** with production values:
   ```yaml
   env_variables:
     FLASK_SECRET_KEY: "your-secure-random-key"
     MAIN_DOMAIN: "https://YOUR_PROJECT_ID.appspot.com"
     ADMIN_BOOTSTRAP_EMAIL: "admin"
     ADMIN_BOOTSTRAP_PASSWORD: "your-secure-password"
     ADMIN_API_KEY: "your-api-key"
     # ... other variables
   ```

2. **Deploy:**
   ```bash
   gcloud app deploy
   ```

3. **View your site:**
   ```bash
   gcloud app browse
   ```

4. **View logs:**
   ```bash
   gcloud app logs tail -s default
   ```

### Setting Up Stripe Webhooks (Production)

1. Go to [Stripe Dashboard → Webhooks](https://dashboard.stripe.com/webhooks)
2. Add endpoint: `https://YOUR_PROJECT_ID.appspot.com/webhook`
3. Select events:
   - `checkout.session.completed`
   - `checkout.session.async_payment_succeeded`
   - `checkout.session.async_payment_failed`
4. Copy the webhook signing secret to `app.yaml`

### Custom Domain Setup

1. Go to App Engine → Settings → Custom Domains
2. Add your domain (e.g., tullhydro.com)
3. Verify ownership and configure DNS
4. Update `MAIN_DOMAIN` in `app.yaml`

### Using Cloud SQL (Recommended for Production)

SQLite on App Engine is ephemeral (data lost on each deploy). For persistent data:

1. **Create a Cloud SQL instance:**
   ```bash
   gcloud sql instances create tull-db --tier=db-f1-micro --region=us-central1
   ```

2. **Create a database:**
   ```bash
   gcloud sql databases create tullhydro --instance=tull-db
   ```

3. **Add to app.yaml:**
   ```yaml
   env_variables:
     DATABASE_URL: "mysql+pymysql://user:pass@/tullhydro?unix_socket=/cloudsql/PROJECT:REGION:INSTANCE"
   
   beta_settings:
     cloud_sql_instances: "PROJECT:REGION:INSTANCE"
   ```

4. **Add to requirements.txt:**
   ```
   PyMySQL==1.1.0
   ```

---

## Stripe Configuration

### Test Mode vs Live Mode

| Mode | Use For | API Keys |
|------|---------|----------|
| Test | Development, testing | `sk_test_...`, `pk_test_...` |
| Live | Production | `sk_live_...`, `pk_live_...` |

### Getting API Keys

1. Go to [Stripe Dashboard](https://dashboard.stripe.com)
2. Toggle "Test mode" for development
3. Go to Developers → API Keys
4. Copy the keys to your environment

### Creating a Product

1. Go to Products in Stripe Dashboard
2. Create a new product (e.g., "Tull Tower V1")
3. Add a price (e.g., $1,500)
4. Copy the Price ID (starts with `price_`)
5. Set `HP_PRICE_ID` in your environment

### Test Card Numbers

For testing payments:

| Card Number | Result |
|-------------|--------|
| 4242 4242 4242 4242 | Success |
| 4000 0000 0000 0002 | Decline |
| 4000 0000 0000 9995 | Insufficient funds |

Use any future expiry date and any 3-digit CVC.

---

## Troubleshooting

### Common Issues

#### "Invalid credentials" on login
- Check that the bootstrap admin was created (look for `[SETUP] Bootstrap admin created` in console output)
- If the database already had users, the bootstrap won't run — manage accounts via the admin API
- For locked accounts: use `POST /api/admin/users/<id>/activate` to unlock

#### "no such column" errors
- The database file predates a schema change and the startup migration did not run
- **Fix:** restart the app (migrations run at startup); if it persists, `python -m xissite.manage_db reset`

#### Static files not loading (404)
- Check that files exist in `xissite/static/`
- Verify URL paths in templates use `url_for('static', filename='...')`

#### Stripe webhook errors
- Verify the webhook URL is correct
- Check the signing secret matches
- For local testing, use [Stripe CLI](https://stripe.com/docs/stripe-cli):
  ```bash
  stripe listen --forward-to localhost:5000/webhook
  ```

#### Database locked (local)
- Close any other programs accessing the database
- Ensure only one instance of the app is running

### Viewing Logs

**Local:**
```bash
# Logs appear in terminal where you ran python main.py
```

**Google Cloud:**
```bash
# Real-time logs
gcloud app logs tail -s default

# Historical logs
gcloud app logs read

# Or use Google Cloud Console → Logging
```

### Getting Help

1. Check the logs for error messages
2. Verify all environment variables are set
3. Test locally before deploying to cloud
4. For Stripe issues, check Stripe Dashboard → Developers → Logs

---

## Security Checklist

Before going to production:

- [ ] Change all default passwords
- [ ] Use strong, unique `FLASK_SECRET_KEY`
- [ ] Use Stripe Live mode keys
- [ ] Verify the Postmark sender signature / domain
- [ ] Configure custom domain with HTTPS
- [ ] Consider Cloud SQL for persistent storage
- [ ] Remove or restrict debug mode
- [ ] Test the complete purchase flow
- [ ] Set up monitoring and alerting

---

## File Reference

```
tull-website/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── app.yaml               # Google Cloud configuration
├── vars.env               # Local environment (DO NOT COMMIT)
├── vars.env.example       # Environment template
├── setup_credentials.py   # Credential generator script
├── MANAGEMENT_GUIDE.md    # This file
├── README.md              # Project overview
│
└── xissite/               # Flask application
    ├── __init__.py        # App factory & database config
    ├── models.py          # Database models
    ├── views.py           # Public routes
    ├── auth.py            # Login, /admin, /ops
    ├── sales.py           # Stripe integration
    ├── admin_api.py       # /api/admin REST API
    ├── spam_guard.py      # Contact-form anti-spam
    ├── email_templates.py # Postmark HTML emails
    ├── timeutil.py        # UTC normalisation for SQLite datetimes
    ├── clientip.py        # Client address rule
    ├── manage_db.py       # Database CLI
    ├── templates/         # HTML templates
    └── static/            # CSS, JS, images, fonts

admin_panel/               # Local admin panel (never deployed)
docs/architecture/         # Visual architecture map
tests/                     # python -m pytest tests/
```
