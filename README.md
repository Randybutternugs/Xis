# Tull Hydroponics Website

A Flask-based e-commerce website for Tull Hydroponics, featuring a brutalist design aesthetic with integrated Stripe payments and customer management.

## Features

- **Brutalist Design**: Clean, minimal black background with strategic green (#6ABD45) accents
- **E-commerce**: Stripe integration for product sales with webhooks for order processing
- **Customer Database**: Admin panel for viewing customers, purchases, and feedback
- **Employee Portal**: Employee access to operational tools pushed by TullOps
- **Contact Form**: Customer feedback system with database storage
- **Mobile First**: Fully responsive design for all devices
- **Auto Environment Detection**: Seamlessly works locally and on Google Cloud

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up credentials (creates vars.env)
python setup_credentials.py

# 3. Run the server
python main.py

# 4. Open http://localhost:5000
#    Login: admin / admin123
```

## Documentation

- **[MANAGEMENT_GUIDE.md](MANAGEMENT_GUIDE.md)** - Complete guide for database, users, and deployment
- **[docs/architecture/xis-architecture-map.html](docs/architecture/xis-architecture-map.html)** - Visual architecture map: system context, request path, routes, flows, data model, security, config (open in a browser)
- **[README.md](README.md)** - This file (project overview)

## Management Scripts

```bash
# Generate a vars.env with a bootstrap admin and fresh keys (interactive)
python setup_credentials.py

# Database CLI (runs on the app's models; honours DATABASE_URL)
python -m xissite.manage_db status      # Row counts for every table
python -m xissite.manage_db customers   # Customers with purchase counts
python -m xissite.manage_db purchases   # Purchases with customer email
python -m xissite.manage_db feedback    # Feedback submissions
python -m xissite.manage_db users       # Accounts (never passwords)
python -m xissite.manage_db export      # customers/purchases/feedback CSV  [--out DIR]
python -m xissite.manage_db backup      # Copy the local SQLite file
python -m xissite.manage_db reset       # Back up, then delete the local SQLite file
```

## Admin Tools

Three ways to look at the site's data, all backed by the same `/api/admin` API:

- **`/admin`** on the site itself: log in as an admin from anywhere. A single-page dashboard for users, logins, customers, orders, feedback, visitors and security, and an Ops section listing what TullOps has pushed to each employee.
- **Local admin panel** (`admin_panel/`): runs on a trusted PC only, never deployed. See [admin_panel/README.md](admin_panel/README.md).
- **TullOps**: calls the API directly with the Bearer key to manage accounts.

Employees log in at the same `/login` and land on `/ops`.

## Project Structure

```
tull-website/
├── main.py                 # Application entry point (gunicorn main:app)
├── requirements.txt        # Python dependencies
├── app.yaml               # Google Cloud App Engine config (gitignored; see app.yaml.example)
├── vars.env               # Local environment (gitignored; see vars.env.example)
├── setup_credentials.py   # Writes vars.env for local development
├── seed_users.py          # Wipes and recreates two named local accounts
├── MANAGEMENT_GUIDE.md    # Database, users, deployment
├── README.md              # This file
├── docs/architecture/     # Visual architecture map (open the .html in a browser)
├── admin_panel/           # Local admin panel (excluded from App Engine by .gcloudignore)
├── tests/                 # Site tests: python -m pytest tests/
│
└── xissite/               # Flask application package
    ├── __init__.py        # App factory, environment detection, migrations, bootstrap admin
    ├── models.py          # Nine SQLAlchemy models
    ├── views.py           # Public pages and the contact form
    ├── auth.py            # Login, /admin, /ops
    ├── sales.py           # Stripe checkout and webhook
    ├── admin_api.py       # /api/admin REST API (Bearer key or admin session)
    ├── spam_guard.py      # Contact-form anti-spam checks
    ├── email_templates.py # Postmark HTML emails
    ├── timeutil.py        # UTC normalisation for datetimes read from SQLite
    ├── clientip.py        # The one rule for a request's client address
    ├── manage_db.py       # Database CLI (see above)
    │
    ├── templates/         # Jinja2 templates
    │   ├── base.html
    │   ├── home.html, about.html, contact.html, sell.html
    │   ├── success.html, cancel.html
    │   ├── loginpage.html
    │   ├── admin_dashboard.html   # /admin shell; data via static/js/admin_dashboard.js
    │   └── employee_ops.html      # /ops (placeholder content today)
    │
    └── static/
        ├── css/main.css, css/dashboard.css
        ├── js/admin_dashboard.js
        ├── icons/, images/, fonts/, scripts/
```

## Deployment

### Local Development
The app automatically detects local development and loads `vars.env`.

### Google Cloud
The app automatically detects Google Cloud and uses `app.yaml` environment variables.

```bash
# Deploy to Google Cloud
gcloud app deploy

# View logs
gcloud app logs tail -s default
```

See [MANAGEMENT_GUIDE.md](MANAGEMENT_GUIDE.md) for complete deployment instructions.

## Local Development

### Prerequisites

- Python 3.10+
- pip

### Setup

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd tull-website
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate     # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp vars.env.example vars.env
   # Edit vars.env with your values
   ```

5. **Run the development server**
   ```bash
   python main.py
   ```

6. **Access the site**
   - Home: http://localhost:5000
   - Admin: http://localhost:5000/login

### Testing Stripe Payments

1. Install [Stripe CLI](https://stripe.com/docs/stripe-cli)

2. Forward webhooks to local server:
   ```bash
   stripe listen --forward-to localhost:5000/webhook
   ```

3. Copy the webhook signing secret to `vars.env`

4. Use test card: `4242 4242 4242 4242`

## Google Cloud Deployment

### Prerequisites

- Google Cloud account with billing enabled
- `gcloud` CLI installed and configured

### Deploy

1. **Update app.yaml**
   - Replace all placeholder values with production credentials
   - Update `MAIN_DOMAIN` to your App Engine URL

2. **Deploy to App Engine**
   ```bash
   gcloud app deploy
   ```

3. **Configure Stripe Webhook**
   - Go to Stripe Dashboard → Webhooks
   - Add endpoint: `https://YOUR_PROJECT.appspot.com/webhook`
   - Select events:
     - `checkout.session.completed`
     - `checkout.session.async_payment_succeeded`
     - `checkout.session.async_payment_failed`

4. **View logs**
   ```bash
   gcloud app logs tail -s default
   ```

### Important Notes

- **Database**: This setup uses SQLite stored in `/tmp` which is ephemeral on App Engine. For production, consider migrating to Cloud SQL.

- **Static Files**: Served directly by App Engine for better performance.

- **Custom Domain**: Configure in App Engine settings after deployment.

## Authentication

The auth system uses database-backed accounts managed by TullOps via the admin API.

**Bootstrap admin** is created on first run from env vars:
- `ADMIN_BOOTSTRAP_EMAIL` — username/email for initial admin
- `ADMIN_BOOTSTRAP_PASSWORD` — password (min 10 chars in production)

**After bootstrap**, all account management happens through the TullOps admin API (`/api/admin/users`).

**Security features:**
- Werkzeug scrypt password hashing
- Per-account lockout (5 failures = 15min, 10 = 1hr)
- Per-IP rate limiting with auto-ban
- 8-hour sessions, 7-day remember-me cookies
- HTTPS-only cookies in production

## Design System

### Colors
| Name | Hex | Usage |
|------|-----|-------|
| Primary | `#000000` | Backgrounds |
| Accent | `#6ABD45` | Highlights, CTAs |
| Text Primary | `#FFFFFF` | Headings |
| Text Secondary | `#CFCFCF` | Body text |
| Text Tertiary | `#666666` | Muted text |
| Input BG | `#111111` | Form fields |
| Border | `#333333` | Dividers |

### Typography
- **Headings**: `pexico_microregular`, uppercase
- **Body**: `HelveticaNeueLT Pro 65 Md`
- **Labels**: `// SECTION NAME` format

### Breakpoints
- Mobile: `max-width: 600px`
- Desktop: `min-width: 601px`

## Routes

### Public
- `GET /` - Home page
- `GET /about` - About page
- `GET /sell` - Product page (currently a "coming soon" layout; no checkout button yet)
- `GET|POST /contact` - Contact form with anti-spam checks; sends confirmation and admin-notification emails
- `POST /create-checkout-session` - Start Stripe Checkout (route is live; nothing links to it while /sell is coming soon)
- `GET /success`, `GET /cancel` - Pages Stripe redirects back to
- `POST /webhook` - Stripe webhook (signature-verified); writes customer and purchase rows

### Login required
- `GET|POST /login` - Admin and employee login (IP bans, rate limits, lockouts; CSRF-checked)
- `GET /logout`
- `GET /admin` - Admin dashboard (admin role)
- `GET /ops` - Employee operations page (employee or admin role)
- `GET /api/ops/me`, `POST /api/ops/items/<id>/events` - Employee's pushed items and actions (session + CSRF header)

### Admin API - `/api/admin`
Accepts either `Authorization: Bearer <ADMIN_API_KEY>` or an admin browser session with an `X-CSRFToken` header on mutations. `GET /api/admin/health` is public.

| Group | Endpoints |
|---|---|
| Stats | `GET /stats` |
| Users | `GET,POST /users` · `PUT,DELETE /users/<id>` · `POST /users/<id>/suspend` · `POST /users/<id>/activate` |
| Logins | `GET /login-attempts` |
| Customers | `GET /customers` · `GET,DELETE /customers/<id>` · `GET /customers/stats` · `GET /customers/geo` |
| Purchases | `GET /purchases` · `GET /purchases/stats` · `GET /purchases/geo` · `GET /purchases/funnel` |
| Feedback | `GET /feedback` · `GET /feedback/stats` · `PUT,DELETE /feedback/<id>` · `POST /feedback/<id>/reply` |
| Visitors | `GET /visitors` · `/visitors/recent` · `/visitors/devices` · `/visitors/referrers` · `/visitors/heatmap` · `/visitors/pageflow` |
| Security | `GET /security/alerts` · `GET /security/login-heatmap` · `POST /security/resolve-geo` · `GET /security/audit-log` |
| Bans | `GET,POST /banned-ips` · `DELETE /banned-ips/<id>` |
| Export | `GET /export/<customers|purchases|feedback|logins>` (CSV) |
| Ops content | `PUT /ops/items/<ref>` · `GET /ops/items` · `DELETE /ops/items/<ref>` · `GET /ops/events?after=` (see `docs/ops-content-push.md`) |

The bootstrap admin (from `ADMIN_BOOTSTRAP_EMAIL`) can never be suspended, deleted or demoted, and a browser session cannot disable its own account.

## License

Proprietary - Tull Hydroponics LLC

## Support

For issues or questions, contact: info@tullhydro.com
