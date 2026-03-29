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

from flask import Blueprint, redirect, url_for, render_template, request, flash, session
from sqlalchemy.sql import func
import os
from werkzeug.security import check_password_hash
from flask_login import login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField
from wtforms.validators import DataRequired, Length
from flask_wtf.csrf import CSRFProtect
from functools import wraps

from . import db
from .models import Customer, FeedBack, Purchase_info, User

# Initialize CSRF protection
csrf = CSRFProtect()

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
    """Decorator to require admin access (not investor)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if session.get('user_type') != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function



# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@auth.route('/login', methods=['GET', 'POST'])       
def login():
    """
    Login page for admin users.

    GET: Displays login form, creates admin user if none exists
    POST: Validates credentials against hashed values in environment variables
          Redirects to admin database viewer on success

    Environment Variables Required:
        ADMIN_USERNAME_HASH: Werkzeug-hashed admin username
        ADMIN_PASSWORD_HASH: Werkzeug-hashed admin password
    """
    csrf.protect()
    form = LoginForm()
    
    # Get hashed credentials from environment
    admin_username_hash = os.environ.get('ADMIN_USERNAME_HASH')
    admin_password_hash = os.environ.get('ADMIN_PASSWORD_HASH')

    # Validate environment configuration
    if not admin_username_hash or not admin_password_hash:
        print("[ERROR] Admin credentials not configured in environment variables")
        flash('System configuration error. Please contact administrator.', 'error')
        return render_template('loginpage.html', form=form)
    
    # On first visit, ensure admin user exists in database
    if request.method == 'GET':
        admin_check = db.session.query(User).first()
        if admin_check is None:
            new_admin = User(email=admin_username_hash, password=admin_password_hash, user_type='admin')
            db.session.add(new_admin)
            db.session.commit()
            print("[SETUP] Admin user created in database")
    
    # Handle login attempt
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        # Check ADMIN credentials first
        admin_username_valid = check_password_hash(admin_username_hash, username)
        admin_password_valid = check_password_hash(admin_password_hash, password)
        
        if admin_username_valid and admin_password_valid:
            user = User.query.filter_by(user_type='admin').first()
            if not user:
                user = User.query.get(1)
            if user:
                login_user(user, remember=True)
                session['user_type'] = 'admin'
                print(f"[AUTH] Successful ADMIN login")
                return redirect(url_for('auth.viewdatabase'))
            else:
                print("[ERROR] Admin user record not found in database")
                flash('Authentication error. Please try again.', 'error')
                return render_template('loginpage.html', form=form)
        
        # Admin credentials did not match
        print("[AUTH] Invalid login attempt")
        flash('Invalid credentials', 'error')

    return render_template('loginpage.html', form=form)


@auth.route('/logout')
@login_required
def logout():
    """Log out the current user and redirect to login page."""
    user_type = session.get('user_type', 'unknown')
    session.pop('user_type', None)
    logout_user()
    print(f"[AUTH] {user_type.upper()} user logged out")
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
