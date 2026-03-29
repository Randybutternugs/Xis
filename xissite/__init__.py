"""
Tull Hydroponics Flask Application Factory
==========================================

This module initializes the Flask application with:
- SQLAlchemy database connection
- CSRF protection
- Flask-Login for admin authentication
- Blueprint registration for routes

AUTOMATIC ENVIRONMENT DETECTION:
    The app automatically detects whether it's running locally or on Google Cloud
    and configures itself appropriately. No code changes needed for deployment.

Environment Variables Required:
- FLASK_SECRET_KEY: Secret key for session management
- ADMIN_BOOTSTRAP_EMAIL: Bootstrap admin username (default: 'admin')
- ADMIN_BOOTSTRAP_PASSWORD: Bootstrap admin password (first-run only)
- STRIPE_SECRET_KEY: Stripe API secret key
- STRIPE_PUBLISHABLE_KEY: Stripe publishable key
- STRIPE_WEBHOOK_SECRET: Stripe webhook signing secret
- HP_PRICE_ID: Stripe Price ID for the product
- MAIL_KEY: Mailgun API key for order confirmations

"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from os import path, environ
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
import uuid
import os
import sys

# ============================================================================
# ENVIRONMENT DETECTION
# ============================================================================

def is_cloud_environment():
    """Check if running on Google Cloud App Engine."""
    return os.environ.get('GAE_ENV', '').startswith('standard') or \
           os.environ.get('GAE_APPLICATION') is not None or \
           os.environ.get('GOOGLE_CLOUD_PROJECT') is not None

def is_development():
    """Check if running in development mode."""
    return os.environ.get('FLASK_ENV') == 'development' or \
           os.environ.get('FLASK_DEBUG') == '1' or \
           not is_cloud_environment()

# Get the directory where this file is located
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ============================================================================
# ENVIRONMENT VARIABLE LOADING
# ============================================================================

if is_cloud_environment():
    print("[CLOUD MODE] Running on Google Cloud - using app.yaml environment variables")
else:
    # Local development - load from vars.env
    possible_env_paths = [
        os.path.join(BASE_DIR, 'vars.env'),
        'vars.env',
        os.path.join(os.path.dirname(__file__), '..', 'vars.env'),
    ]
    
    env_loaded = False
    for env_path in possible_env_paths:
        if os.path.exists(env_path):
            try:
                from dotenv import load_dotenv
                load_dotenv(env_path)
                print(f"[DEV MODE] Loaded environment from {env_path}")
                env_loaded = True
                break
            except ImportError:
                print("[WARNING] python-dotenv not installed. Run: pip install python-dotenv")
                break
    
    if not env_loaded:
        print("[WARNING] No vars.env found. Copy vars.env.example to vars.env and configure it.")

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

db = SQLAlchemy()
DB_NAME = "tullhydro.db"

def get_database_uri():
    """
    Get the appropriate database URI based on environment.
    
    Local Development: SQLite file in project directory
    Google Cloud: SQLite in /tmp (ephemeral) or Cloud SQL if configured
    
    Returns:
        str: SQLAlchemy database URI
    """
    # Check for Cloud SQL configuration first (production-ready)
    cloud_sql_uri = os.environ.get('DATABASE_URL') or os.environ.get('CLOUD_SQL_URI')
    if cloud_sql_uri:
        print(f"[DATABASE] Using Cloud SQL")
        return cloud_sql_uri
    
    # Fall back to SQLite
    if is_cloud_environment():
        # Google App Engine - use /tmp for writable storage
        db_path = f'/tmp/{DB_NAME}'
        print(f"[DATABASE] Using SQLite at {db_path} (ephemeral - resets on deploy)")
        return f'sqlite:///{db_path}'
    else:
        # Local development - use project directory
        db_path = os.path.join(BASE_DIR, DB_NAME)
        print(f"[DATABASE] Using SQLite at {db_path}")
        return f'sqlite:///{db_path}'


def create_app():
    """
    Application factory function.
    
    Automatically configures for local development or cloud deployment.
    
    Returns:
        Flask: Configured Flask application instance
    """
    app = Flask(__name__)
    
    # ========================================================================
    # CONFIGURATION
    # ========================================================================
    
    # Secret key
    secret_key = os.environ.get('FLASK_SECRET_KEY')
    if not secret_key:
        if is_cloud_environment():
            print("[ERROR] FLASK_SECRET_KEY must be set in app.yaml for production!")
            secret_key = str(uuid.uuid4())  # Temporary fallback
        else:
            print("[WARNING] No FLASK_SECRET_KEY set, using generated key (OK for development)")
            secret_key = 'dev-secret-key-' + str(uuid.uuid4())
    app.config['SECRET_KEY'] = secret_key
    
    # Database
    app.config['SQLALCHEMY_DATABASE_URI'] = get_database_uri()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,  # Verify connections before use
    }
    
    # CSRF
    app.config['WTF_CSRF_CHECK_DEFAULT'] = False
    
    # Debug mode (auto-detected)
    app.config['DEBUG'] = is_development()
    
    # ========================================================================
    # EXTENSIONS
    # ========================================================================
    
    csrf = CSRFProtect()
    csrf.init_app(app)
    db.init_app(app)
    
    # ========================================================================
    # BLUEPRINTS
    # ========================================================================
    
    from .views import views
    from .auth import auth
    from .sales import sales
    from .admin_api import admin_api

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(sales, url_prefix='/')
    app.register_blueprint(admin_api)
    
    # ========================================================================
    # DATABASE INITIALIZATION & MIGRATION
    # ========================================================================
    
    from .models import (Customer, Purchase_info, User, FeedBack,
                         LoginAttempt, SiteVisit, BannedIP, GeoIPCache,
                         AdminAuditLog)
    create_database(app)
    
    # ========================================================================
    # LOGIN MANAGER
    # ========================================================================
    
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))
    
    # ========================================================================
    # STARTUP INFO
    # ========================================================================
    
    print("=" * 60)
    print("TULL HYDROPONICS")
    print("=" * 60)
    print(f"  Environment: {'CLOUD' if is_cloud_environment() else 'LOCAL DEVELOPMENT'}")
    print(f"  Debug Mode:  {app.config['DEBUG']}")
    print(f"  Database:    {app.config['SQLALCHEMY_DATABASE_URI'][:50]}...")
    print("=" * 60)

    return app


def create_database(app):
    """
    Creates database tables and runs any necessary migrations.
    
    Handles:
    - Initial table creation
    - Adding new columns to existing tables (migrations)
    - Cloud vs local database differences
    
    Args:
        app: Flask application instance
    """
    with app.app_context():
        # Create all tables
        db.create_all()
        print('[DATABASE] Tables created/verified')

        # Run migrations for existing databases
        run_migrations()

        from .models import User

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


def run_migrations():
    """
    Run database migrations for schema changes.
    
    This handles upgrading existing databases when the schema changes,
    without requiring users to delete their database.
    """
    migrations = [
        {
            'name': 'add_user_type_column',
            'check': "SELECT * FROM pragma_table_info('user') WHERE name='user_type'",
            'migrate': "ALTER TABLE user ADD COLUMN user_type VARCHAR(50) DEFAULT 'admin'"
        },
        {
            'name': 'add_product_name_column',
            'check': "SELECT * FROM pragma_table_info('purchase__info') WHERE name='product_name'",
            'migrate': "ALTER TABLE purchase__info ADD COLUMN product_name VARCHAR(100) DEFAULT 'Tull Tower V1'"
        },
        {
            'name': 'add_feedback_submitter_ip',
            'check': "SELECT * FROM pragma_table_info('feed_back') WHERE name='submitter_ip'",
            'migrate': "ALTER TABLE feed_back ADD COLUMN submitter_ip VARCHAR(45)"
        },
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
    ]
    
    from sqlalchemy import text
    
    try:
        with db.engine.connect() as conn:
            for migration in migrations:
                try:
                    result = conn.execute(text(migration['check']))
                    if result.fetchone() is None:
                        print(f"[MIGRATION] Running: {migration['name']}")
                        conn.execute(text(migration['migrate']))
                        conn.commit()
                        print(f"[MIGRATION] Complete: {migration['name']}")
                except Exception as e:
                    # Migration might fail if table doesn't exist yet - that's OK
                    pass
    except Exception as e:
        print(f"[MIGRATION] Skipped (new database): {e}")
