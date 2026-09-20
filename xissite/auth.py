"""
Authentication & Dashboard Routes
=================================

This module handles:
- Admin and employee login/logout
- /admin (single-page admin dashboard, data via /api/admin)
- /ops (employee operations page)

All routes except /login require authentication via Flask-Login.
"""

from datetime import datetime, timedelta, timezone

from flask import Blueprint, redirect, url_for, render_template, request, flash
import os
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField
from wtforms.validators import DataRequired
from functools import wraps

from . import db
from .models import User
from .timeutil import as_utc
from .clientip import client_ip as client_address

# Create Blueprint
auth = Blueprint('auth', __name__)


# ============================================================================
# FORMS
# ============================================================================

class LoginForm(FlaskForm):
    """Admin login form with username and password fields."""
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Authenticate')


# ============================================================================
# CUSTOM DECORATORS
# ============================================================================

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



# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@auth.route('/login', methods=['GET', 'POST'])
def login():
    """
    Login page for Admin and Employee users.
    POST: Validates credentials against User table in database.
    """
    form = LoginForm()

    # validate_on_submit() checks the CSRF token the template renders and the
    # required fields. A form that fails it is not a login attempt.
    if request.method == 'POST' and not form.validate_on_submit():
        flash('The form could not be verified. Please reload the page and try again.', 'error')
        return render_template('loginpage.html', form=form)

    if request.method == 'POST':
        from .models import BannedIP, LoginAttempt as LA
        client_ip = client_address()

        username = form.username.data.strip()
        password = form.password.data

        user = User.query.filter_by(email=username).first()
        is_admin = user is not None and user.user_type == 'admin'

        # Admin bypasses all IP-level restrictions
        if not is_admin:
            # Check if IP is banned
            active_ban = BannedIP.query.filter_by(
                ip_address=client_ip, active=True
            ).first()
            if active_ban:
                if active_ban.expires_at and as_utc(active_ban.expires_at) < datetime.now(timezone.utc):
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

        success = False
        failure_reason = None

        if user is None:
            # Dummy hash check to prevent timing-based username enumeration
            check_password_hash(generate_password_hash('dummy'), password)
            failure_reason = 'unknown_user'
        elif user.status == 'suspended':
            # Applies to admins too. The bootstrap admin can never be
            # suspended (admin_api refuses), so this cannot lock out recovery.
            failure_reason = 'account_suspended'
            flash('Account suspended. Contact your administrator.', 'error')
        elif user.status == 'deleted':
            failure_reason = 'unknown_user'
        elif not is_admin and user.locked_until and as_utc(user.locked_until) > datetime.now(timezone.utc):
            remaining = int((as_utc(user.locked_until) - datetime.now(timezone.utc)).total_seconds() / 60) + 1
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
            # Admin login lifts any active IP ban on their address
            if is_admin:
                active_bans = BannedIP.query.filter_by(
                    ip_address=client_ip, active=True
                ).all()
                for ban in active_bans:
                    ban.active = False
                if active_bans:
                    print(f"[AUTH] Admin login lifted {len(active_bans)} IP ban(s) on {client_ip}")
            db.session.commit()
            login_user(user, remember=True)
            print(f"[AUTH] Successful {user.user_type.upper()} login: {username}")
            if user.user_type == 'admin':
                return redirect(url_for('auth.admin_dashboard'))
            else:
                return redirect(url_for('auth.employee_ops'))
        else:
            if user and failure_reason == 'invalid_password' and not is_admin:
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


@auth.route('/logout')
@login_required
def logout():
    """Log out the current user and redirect to login page."""
    print(f"[AUTH] {current_user.user_type.upper()} user logged out")
    logout_user()
    return redirect(url_for('auth.login'))


@auth.route('/ops')
@login_required
@employee_required
def employee_ops():
    """Employee operations center -- TullOps-pushed content appears here."""
    return render_template('employee_ops.html', user=current_user)


@auth.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    """Admin dashboard -- single-page view of all site data."""
    return render_template('admin_dashboard.html')
