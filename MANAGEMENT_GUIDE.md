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
| Investor | investor | invest123 |

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
| `ADMIN_USERNAME_HASH` | Yes | Werkzeug hash of admin username |
| `ADMIN_PASSWORD_HASH` | Yes | Werkzeug hash of admin password |
| `INVESTOR_USERNAME_HASH` | No | Werkzeug hash of investor username |
| `INVESTOR_PASSWORD_HASH` | No | Werkzeug hash of investor password |
| `STRIPE_SECRET_KEY` | Yes | Stripe API secret key |
| `STRIPE_PUBLISHABLE_KEY` | Yes | Stripe API publishable key |
| `STRIPE_WEBHOOK_SECRET` | Yes | Stripe webhook signing secret |
| `HP_PRICE_ID` | Yes | Stripe Price ID for your product |
| `MAIL_KEY` | Yes | Mailgun API key |
| `MAIN_DOMAIN` | Yes | Your domain (e.g., https://tullhydro.com) |

---

## User Management

### Understanding User Types

| User Type | Access | Destination After Login |
|-----------|--------|------------------------|
| `admin` | Customer database, purchases, feedback | `/viewdb` |
| `investor` | Investor portal only | `/investor` |

### Generating Password Hashes

Use Python to generate secure password hashes:

```python
from werkzeug.security import generate_password_hash

# Generate hashes for your credentials
username = "your_username"
password = "your_secure_password"

print(f"Username hash: {generate_password_hash(username)}")
print(f"Password hash: {generate_password_hash(password)}")
```

Or use the setup script:

```bash
python setup_credentials.py
```

### Adding a New Admin

1. Generate hashes for the new credentials
2. Update `vars.env` (local) or `app.yaml` (cloud)
3. Restart the application

### Adding a New Investor Account

1. Generate hashes:
   ```python
   from werkzeug.security import generate_password_hash
   print(generate_password_hash("investor_username"))
   print(generate_password_hash("investor_password"))
   ```

2. Add to environment:
   ```
   INVESTOR_USERNAME_HASH=scrypt:32768:8:1$...
   INVESTOR_PASSWORD_HASH=scrypt:32768:8:1$...
   ```

3. Restart the application

### Changing Passwords

1. Generate a new hash for the new password
2. Replace the old hash in `vars.env` or `app.yaml`
3. Restart the application

**Note:** Users in the database are created automatically on first login. The hashes in environment variables are the source of truth.

---

## Database Management

### Database Location

| Environment | Location | Persistence |
|-------------|----------|-------------|
| Local | `./tullhydro.db` | Permanent |
| Google Cloud (SQLite) | `/tmp/tullhydro.db` | Ephemeral (resets on deploy) |
| Google Cloud (Cloud SQL) | Cloud SQL instance | Permanent |

### Viewing the Database (Local)

#### Using Python

```python
import sqlite3

conn = sqlite3.connect('tullhydro.db')
cursor = conn.cursor()

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print(cursor.fetchall())

# View all customers
cursor.execute("SELECT * FROM customer")
for row in cursor.fetchall():
    print(row)

# View all purchases
cursor.execute("SELECT * FROM purchase__info")
for row in cursor.fetchall():
    print(row)

# View all feedback
cursor.execute("SELECT * FROM feed_back")
for row in cursor.fetchall():
    print(row)

# View all users
cursor.execute("SELECT * FROM user")
for row in cursor.fetchall():
    print(row)

conn.close()
```

#### Using DB Browser for SQLite

1. Download [DB Browser for SQLite](https://sqlitebrowser.org/)
2. Open `tullhydro.db`
3. Browse tables visually

#### Using the Admin Panel

Login as admin at `/login` to access:
- `/viewdb` - Customer list with search
- `/viewdb/<id>` - Customer details and purchase history
- `/viewdb/feedbackview` - All feedback submissions

### Database Schema

```
customer
├── id (INTEGER, PRIMARY KEY)
├── email (VARCHAR 150, UNIQUE)
├── first_name (VARCHAR 150)
├── last_name (VARCHAR 150)
└── creation_date (DATETIME)

purchase__info
├── id (INTEGER, PRIMARY KEY)
├── customer_id (INTEGER, FOREIGN KEY -> customer.id)
├── product_name (VARCHAR 100)
├── purchase_date (DATETIME)
├── address (VARCHAR 10000)
└── paid (BOOLEAN)

feed_back
├── id (INTEGER, PRIMARY KEY)
├── feedbackmail (VARCHAR 150)
├── feedbacktype (VARCHAR 50)
├── feedbackorderid (VARCHAR 100)
└── feedbackfullfield (VARCHAR 10000)

user
├── id (INTEGER, PRIMARY KEY)
├── email (VARCHAR 150)
├── password (VARCHAR 150)
└── user_type (VARCHAR 50)
```

### Backing Up the Database (Local)

```bash
# Simple copy
cp tullhydro.db tullhydro_backup_$(date +%Y%m%d).db

# With SQLite tools
sqlite3 tullhydro.db ".backup 'backup.db'"
```

### Resetting the Database

```bash
# Delete the database file
rm tullhydro.db  # Linux/Mac
del tullhydro.db # Windows

# Restart the application - tables will be recreated
python main.py
```

### Exporting Data to CSV

```python
import sqlite3
import csv

conn = sqlite3.connect('tullhydro.db')
cursor = conn.cursor()

# Export customers
cursor.execute("SELECT * FROM customer")
with open('customers.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['id', 'email', 'first_name', 'last_name', 'creation_date'])
    writer.writerows(cursor.fetchall())

# Export purchases
cursor.execute("SELECT * FROM purchase__info")
with open('purchases.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['id', 'customer_id', 'product_name', 'purchase_date', 'address', 'paid'])
    writer.writerows(cursor.fetchall())

conn.close()
print("Exported to customers.csv and purchases.csv")
```

### Database Migrations

The app automatically handles migrations when you update the code. Current migrations:
- `add_user_type_column` - Adds user_type to existing user tables
- `add_product_name_column` - Adds product_name to existing purchase tables

Migrations run automatically on startup if needed.

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
     ADMIN_USERNAME_HASH: "scrypt:32768:8:1$..."
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

#### "Admin credentials not configured"
- Check that `ADMIN_USERNAME_HASH` and `ADMIN_PASSWORD_HASH` are set
- For local: Verify `vars.env` exists and has correct values
- For cloud: Check `app.yaml` environment variables

#### "no such column: user.user_type"
- Your database is from an older version
- **Fix:** Delete `tullhydro.db` and restart, OR the app will auto-migrate

#### "Invalid credentials" on login
- The password hash might be incorrect
- Regenerate the hash:
  ```python
  from werkzeug.security import generate_password_hash
  print(generate_password_hash("your_password"))
  ```

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
- [ ] Set up proper Mailgun domain
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
    ├── auth.py            # Authentication & admin routes
    ├── sales.py           # Stripe integration
    ├── templates/         # HTML templates
    └── static/            # CSS, JS, images, fonts
```
