"""
Seed Users Script
=================

One-time script to set up initial admin and employee credentials.
Wipes all existing users and creates fresh accounts.

Usage:
    python seed_users.py
"""

import os
import secrets
import string

# Point to in-project SQLite so the seed hits the real local DB
os.environ.setdefault('FLASK_ENV', 'development')

from werkzeug.security import generate_password_hash
from xissite import create_app, db
from xissite.models import User


def generate_password(length=16):
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + '!@#$%&*'
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def seed():
    app = create_app()
    with app.app_context():
        # Wipe all existing users
        existing = User.query.all()
        if existing:
            for u in existing:
                db.session.delete(u)
            db.session.commit()
            print(f'[SEED] Deleted {len(existing)} existing user(s)')

        # Generate passwords
        adonis_pw = generate_password()
        patrick_pw = generate_password()

        # Create Adonis (admin)
        admin = User(
            email='adonis',
            password=generate_password_hash(adonis_pw),
            user_type='admin',
            status='active',
            display_name='Adonis',
        )
        db.session.add(admin)

        # Create Patrick (employee)
        employee = User(
            email='patrick',
            password=generate_password_hash(patrick_pw),
            user_type='employee',
            status='active',
            display_name='Patrick Trabulsi',
        )
        db.session.add(employee)

        db.session.commit()

        print()
        print('=' * 50)
        print('  CREDENTIALS -- SAVE THESE NOW')
        print('=' * 50)
        print()
        print(f'  ADMIN')
        print(f'    Username: adonis')
        print(f'    Password: {adonis_pw}')
        print(f'    Role:     admin')
        print()
        print(f'  EMPLOYEE')
        print(f'    Username: patrick')
        print(f'    Password: {patrick_pw}')
        print(f'    Role:     employee')
        print()
        print('=' * 50)
        print('  Change passwords later via TullOps admin API.')
        print('=' * 50)


if __name__ == '__main__':
    seed()
