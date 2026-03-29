import os
import pytest

# Set test env vars before importing app
os.environ['FLASK_SECRET_KEY'] = 'test-secret-key-for-testing-only'
os.environ['ADMIN_BOOTSTRAP_EMAIL'] = 'admin'
os.environ['ADMIN_BOOTSTRAP_PASSWORD'] = 'testpassword123'
os.environ['FLASK_ENV'] = 'development'
# Force in-memory SQLite before create_app() reads the URI (DATABASE_URL is
# checked first in get_database_uri(), so this overrides the file-based path
# and ensures create_database() also targets :memory:).
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

from xissite import create_app, db as _db


@pytest.fixture(scope='session')
def app():
    """Create a Flask app configured for testing."""
    app = create_app()
    app.config['TESTING'] = True
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
