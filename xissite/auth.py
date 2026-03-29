"""
Authentication & Database Viewer Routes
=======================================

This module handles:
- Admin login/logout authentication
- Customer database viewer (protected routes)
- Search functionality for customers and orders
- Feedback viewer for customer submissions

All routes except /login require authentication via Flask-Login.
"""

from datetime import datetime, timedelta, timezone

from flask import Blueprint, redirect, url_for, render_template, request, flash
from sqlalchemy.sql import func
import os
from werkzeug.security import check_password_hash
from flask_login import login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField
from wtforms.validators import DataRequired, Length
from functools import wraps

from . import db
from .models import Customer, FeedBack, Purchase_info, User

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


class SearchForm(FlaskForm):
    """Search form for finding customers by email or purchase ID."""
    SearchWord = StringField('', validators=[DataRequired(), Length(min=1, max=40)])
    submit = SubmitField('')


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

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()

        user = User.query.filter_by(email=username).first()

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


@auth.route('/logout')
@login_required
def logout():
    """Log out the current user and redirect to login page."""
    print(f"[AUTH] {current_user.user_type.upper()} user logged out")
    logout_user()
    return redirect(url_for('auth.login'))


# ============================================================================
# DATABASE VIEWER ROUTES (Admin Only)
# ============================================================================

@auth.route('/viewdb', methods=['GET', 'POST'])
@login_required
@admin_required
def viewdatabase():
    """
    Main database viewer page (Admin only).
    
    Displays all customers with search functionality.
    Search supports:
        - Email addresses (containing @)
        - Purchase IDs (numeric strings)
    """
    customerinf = Customer.query.order_by(Customer.id.desc())
    form = SearchForm()
    
    if form.validate_on_submit():
        search_term = form.SearchWord.data.strip()
        
        if "@" in search_term:
            # Search by email
            customer = Customer.query.filter_by(email=search_term).first()
            if customer:
                return redirect(f'/viewdb/{customer.id}')
            else:
                flash('Email not found in database')
        else:
            # Search by purchase ID
            purchase = Purchase_info.query.filter_by(id=search_term).first()
            if purchase:
                return redirect(f'/viewdb/{purchase.customer_id}')
            else:
                flash('Purchase ID not found in database')
                
    return render_template('show.html', customerinf=customerinf, form=form)


@auth.route('/viewdb/<int:customerid>', methods=['GET'])
@login_required
@admin_required
def viewcustomer(customerid):
    """
    Detailed view of a single customer and their purchase history (Admin only).
    
    Args:
        customerid: Database ID of the customer to view
    """
    customer_info = Customer.query.get_or_404(customerid)
    
    # Count total purchases for this customer
    customer_purchasesno = db.session.query(func.count(Purchase_info.id))\
        .filter(Purchase_info.customer_id == customerid)\
        .scalar()
    
    # Get all purchases, ordered by date (most recent last)
    customer_purchase_info = Purchase_info.query\
        .filter_by(customer_id=customerid)\
        .order_by(Purchase_info.purchase_date.asc())\
        .all()
    
    return render_template(
        'showmore.html', 
        customer_info=customer_info, 
        customer_purchase_info=customer_purchase_info, 
        customer_purchasesno=customer_purchasesno
    )


@auth.route('/viewdb/feedbackview', methods=['GET'])
@login_required
@admin_required
def viewfeedback():
    """
    View all customer feedback submissions (Admin only).
    
    Displays feedback ordered by most recent first.
    """
    feedback_info = FeedBack.query.order_by(FeedBack.id.desc())
    return render_template('feedbackview.html', feedback_info=feedback_info)
