# Tull Hydroponics Website

A Flask-based e-commerce website for Tull Hydroponics, featuring a brutalist design aesthetic with integrated Stripe payments and customer management.

## Features

- **Brutalist Design**: Clean, minimal black background with strategic green (#6ABD45) accents
- **E-commerce**: Stripe integration for product sales with webhooks for order processing
- **Customer Database**: Admin panel for viewing customers, purchases, and feedback
- **Investor Portal**: Separate login for investors with confidential materials
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
- **[README.md](README.md)** - This file (project overview)

## Management Scripts

```bash
# Generate login credentials
python setup_credentials.py

# Database management
python manage_db.py status     # Show database status
python manage_db.py customers  # List customers
python manage_db.py purchases  # List purchases
python manage_db.py export     # Export to CSV
python manage_db.py backup     # Create backup
```

## Project Structure

```
tull-website/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── app.yaml               # Google Cloud App Engine config
├── vars.env               # Local environment (DO NOT COMMIT)
├── vars.env.example       # Environment template
├── setup_credentials.py   # Credential generator
├── manage_db.py           # Database management CLI
├── MANAGEMENT_GUIDE.md    # Complete management guide
├── README.md              # This file
│
└── xissite/               # Flask application package
    ├── __init__.py        # App factory (auto-detects environment)
    ├── models.py          # Database models
    ├── views.py           # Public routes (home, about, contact)
    ├── auth.py            # Authentication & admin routes
    ├── sales.py           # Stripe checkout & webhooks
    │
    ├── templates/         # Jinja2 templates
    │   ├── base.html
    │   ├── home.html
    │   ├── about.html
    │   ├── contact.html
    │   ├── sell.html
    │   ├── success.html
    │   ├── cancel.html
    │   ├── loginpage.html
    │   ├── investor.html      # Investor portal
    │   ├── show.html          # Customer list
    │   ├── showmore.html      # Customer detail
    │   ├── feedbackview.html  # Feedback list
    │   └── dataviz.html
    │
    └── static/
        ├── css/main.css
        ├── icons/*.svg
        ├── images/
        ├── fonts/
        └── scripts/
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

## Admin Credentials

Generate hashed credentials:

```python
from werkzeug.security import generate_password_hash

username_hash = generate_password_hash('your_username')
password_hash = generate_password_hash('your_password')

print(f"ADMIN_USERNAME_HASH={username_hash}")
print(f"ADMIN_PASSWORD_HASH={password_hash}")
```

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

## API Endpoints

### Public
- `GET /` - Home page
- `GET /about` - About page
- `GET /contact` - Contact form
- `POST /contact` - Submit feedback
- `GET /sell` - Product page
- `POST /create-checkout-session` - Start Stripe checkout
- `GET /success` - Payment success
- `GET /cancel` - Payment cancelled

### Protected (require login)
- `GET /login` - Login page
- `POST /login` - Authenticate
- `GET /logout` - Logout
- `GET /viewdb` - Customer list
- `GET /viewdb/<id>` - Customer detail
- `GET /viewdb/feedbackview` - Feedback list

### Webhooks
- `POST /webhook` - Stripe webhook handler

## License

Proprietary - Tull Hydroponics LLC

## Support

For issues or questions, contact: info@tullhydro.com
