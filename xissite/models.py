"""
Database Models for Tull Hydroponics Website
============================================

This module defines the SQLAlchemy models for:
- User: Admin authentication
- Customer: Customer information from purchases
- Purchase_info: Individual purchase records
- FeedBack: Customer feedback submissions

Usage:
    from .models import Customer, Purchase_info, User, FeedBack
"""

from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func
import os

# ============================================================================
# FEEDBACK MODEL
# ============================================================================
class FeedBack(db.Model):
    """
    Stores customer feedback submissions from the contact form.
    
    Attributes:
        id: Primary key
        feedbackmail: Email address of the person submitting feedback
        feedbacktype: Type of feedback ('1' = General, '2' = Order-related)
        feedbackorderid: Optional order ID if feedback relates to a purchase
        feedbackfullfield: The actual feedback content
        date: Timestamp of when feedback was submitted
    """
    __tablename__ = 'feed_back'
    
    id = db.Column(db.Integer, primary_key=True)
    feedbackmail = db.Column(db.String(150))
    feedbacktype = db.Column(db.String(50))
    feedbackorderid = db.Column(db.String(50), nullable=True)
    feedbackfullfield = db.Column(db.String(10000))
    date = db.Column(db.DateTime(timezone=True), default=func.now())

    def __repr__(self):
        return f'<FeedBack {self.id} - {self.feedbackmail}>'


# ============================================================================
# USER MODEL (Admin/Investor Authentication)
# ============================================================================
class User(db.Model, UserMixin):
    """
    User model for admin and investor authentication.
    
    Supports multiple user types:
    - 'admin': Full access to database viewer, customer info, feedback
    - 'investor': Access to investor portal only
    
    Note: Passwords are stored as hashed values using Werkzeug's 
    generate_password_hash function.
    
    Attributes:
        id: Primary key
        email: Hashed username (stored as email field for compatibility)
        password: Hashed password
        user_type: Type of user ('admin' or 'investor')
    """
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    user_type = db.Column(db.String(50), default='admin')  # 'admin' or 'investor'

    def __repr__(self):
        return f'<User {self.id} - {self.user_type}>'


# ============================================================================
# CUSTOMER MODEL
# ============================================================================
class Customer(db.Model):
    """
    Stores customer information from completed purchases.
    
    Customers are identified by email - returning customers will have
    new purchases linked to their existing record.
    
    Attributes:
        id: Primary key
        email: Customer's email address
        name: Customer's full name
        creation_date: When the customer record was created
        buys: Relationship to associated purchases
    """
    __tablename__ = 'customer'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), nullable=False)
    name = db.Column(db.String(150))
    creation_date = db.Column(db.DateTime(timezone=True), default=func.now())
    buys = db.relationship('Purchase_info', backref='customer', lazy=True)

    def __repr__(self):
        return f'<Customer {self.id} - {self.email}>'


# ============================================================================
# PURCHASE INFO MODEL
# ============================================================================
class Purchase_info(db.Model):
    """
    Stores individual purchase records with shipping details.
    
    Each purchase is linked to a Customer record. The shipping address
    and payment status are captured from Stripe webhooks.
    
    Attributes:
        id: Primary key (can be used as order reference number)
        product_name: Name of the purchased product
        city, country, line1, line2, postal_code, state: Shipping address
        pay_status: Payment status from Stripe ('paid', 'pending', etc.)
        purchase_date: When the purchase was made
        customer_id: Foreign key to the customer who made the purchase
    """
    __tablename__ = 'purchase_info'
    
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(150), default="Tull Tower V1")
    city = db.Column(db.String(150))
    country = db.Column(db.String(150))
    line1 = db.Column(db.String(150))
    line2 = db.Column(db.String(150))
    postal_code = db.Column(db.String(150))
    state = db.Column(db.String(150))
    pay_status = db.Column(db.String(150))
    purchase_date = db.Column(db.DateTime(timezone=True), default=func.now())
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'))

    def __repr__(self):
        return f'<Purchase {self.id} - {self.product_name}>'
