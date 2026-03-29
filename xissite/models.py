"""
Database Models for Tull Hydroponics Website
============================================

This module defines the SQLAlchemy models for:
- User: Admin authentication
- LoginAttempt: Tracks login attempts for security monitoring
- BannedIP: IP addresses banned from the site
- SiteVisit: Page visit tracking
- GeoIPCache: Cached GeoIP lookups
- AdminAuditLog: Admin action audit trail
- Customer: Customer information from purchases
- Purchase_info: Individual purchase records
- FeedBack: Customer feedback submissions

Usage:
    from .models import Customer, Purchase_info, User, FeedBack
    from .models import LoginAttempt, BannedIP, SiteVisit, GeoIPCache, AdminAuditLog
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
        submitter_ip: IP address of the submitter
        resolved: Whether the feedback has been resolved
        admin_notes: Internal notes from admin
        serial_number: Optional serial number associated with feedback
        first_response_date: When admin first responded
        resolved_date: When the feedback was resolved
        resolution_time_hours: Time taken to resolve in hours
    """
    __tablename__ = 'feed_back'

    id = db.Column(db.Integer, primary_key=True)
    feedbackmail = db.Column(db.String(150))
    feedbacktype = db.Column(db.String(50))
    feedbackorderid = db.Column(db.String(50), nullable=True)
    feedbackfullfield = db.Column(db.String(10000))
    date = db.Column(db.DateTime(timezone=True), default=func.now())
    submitter_ip = db.Column(db.String(45), nullable=True)
    resolved = db.Column(db.Boolean, default=False)
    admin_notes = db.Column(db.Text, nullable=True)
    serial_number = db.Column(db.String(100), nullable=True)
    first_response_date = db.Column(db.DateTime, nullable=True)
    resolved_date = db.Column(db.DateTime, nullable=True)
    resolution_time_hours = db.Column(db.Integer, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'feedbackmail': self.feedbackmail,
            'feedbacktype': self.feedbacktype,
            'feedbackorderid': self.feedbackorderid,
            'feedbackfullfield': self.feedbackfullfield,
            'date': self.date.isoformat() if self.date else None,
            'submitter_ip': self.submitter_ip,
            'resolved': self.resolved,
            'admin_notes': self.admin_notes,
            'serial_number': self.serial_number,
            'first_response_date': self.first_response_date.isoformat() if self.first_response_date else None,
            'resolved_date': self.resolved_date.isoformat() if self.resolved_date else None,
            'resolution_time_hours': self.resolution_time_hours,
        }

    def __repr__(self):
        return f'<FeedBack {self.id} - {self.feedbackmail}>'


# ============================================================================
# USER MODEL (Admin/Employee Authentication)
# ============================================================================
class User(db.Model, UserMixin):
    """
    User model for admin and employee authentication.

    Supports two user types:
    - 'admin': Full access to database viewer, customer info, feedback
    - 'employee': Employee access to operational tools pushed by TullOps

    Passwords are stored as Werkzeug scrypt hashes.
    Accounts are managed remotely by TullOps via the admin API.

    Attributes:
        id: Primary key
        email: Username or email address used for login
        password: Werkzeug scrypt hash
        user_type: 'admin' or 'employee'
        status: Account status ('active', 'suspended', 'deleted')
        display_name: Human-readable display name
        notes: Internal admin notes
        last_login: Timestamp of last successful login
        failed_attempts: Count of consecutive failed login attempts
        locked_until: Timestamp until which the account is locked
        created_at: Timestamp when the account was created
    """
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(256))
    user_type = db.Column(db.String(50), default='employee')
    status = db.Column(db.String(50), default='active')
    display_name = db.Column(db.String(150), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    last_login = db.Column(db.DateTime, nullable=True)
    failed_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'user_type': self.user_type,
            'status': self.status,
            'display_name': self.display_name,
            'notes': self.notes,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'failed_attempts': self.failed_attempts,
            'locked_until': self.locked_until.isoformat() if self.locked_until else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<User {self.id} - {self.user_type}>'


# ============================================================================
# LOGIN ATTEMPT MODEL
# ============================================================================
class LoginAttempt(db.Model):
    """
    Tracks login attempts for security monitoring and brute-force detection.

    Attributes:
        id: Primary key
        ip_address: IP address of the requester (IPv4 or IPv6)
        user_agent: Browser/client user agent string
        username_attempted: The username/email that was tried
        success: Whether the login succeeded
        failure_reason: Why the login failed (e.g. 'invalid_password', 'banned_ip')
        user_type_matched: The user_type of the matched user, if any
        timestamp: When the attempt occurred
    """
    __tablename__ = 'login_attempt'

    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), index=True)
    user_agent = db.Column(db.String(500))
    username_attempted = db.Column(db.String(150))
    success = db.Column(db.Boolean, default=False)
    failure_reason = db.Column(db.String(100))
    user_type_matched = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime(timezone=True), default=func.now(), index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'username_attempted': self.username_attempted,
            'success': self.success,
            'failure_reason': self.failure_reason,
            'user_type_matched': self.user_type_matched,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }

    def __repr__(self):
        return f'<LoginAttempt {self.id} - {self.ip_address} - {"ok" if self.success else "fail"}>'


# ============================================================================
# BANNED IP MODEL
# ============================================================================
class BannedIP(db.Model):
    """
    Stores IP addresses that are banned from accessing the site.

    Attributes:
        id: Primary key
        ip_address: The banned IP address
        reason: Why the IP was banned
        banned_by: Who/what issued the ban (e.g. 'auto', admin email)
        active: Whether the ban is currently active
        created_date: When the ban was created
        expires_at: Optional expiry datetime (None = permanent)
    """
    __tablename__ = 'banned_ip'

    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    reason = db.Column(db.String(200))
    banned_by = db.Column(db.String(50))
    active = db.Column(db.Boolean, default=True)
    created_date = db.Column(db.DateTime(timezone=True), default=func.now())
    expires_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'ip_address': self.ip_address,
            'reason': self.reason,
            'banned_by': self.banned_by,
            'active': self.active,
            'created_date': self.created_date.isoformat() if self.created_date else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
        }

    def __repr__(self):
        return f'<BannedIP {self.id} - {self.ip_address} - {"active" if self.active else "inactive"}>'


# ============================================================================
# SITE VISIT MODEL
# ============================================================================
class SiteVisit(db.Model):
    """
    Tracks page visits for analytics.

    Attributes:
        id: Primary key
        ip_address: Visitor IP address
        path: URL path visited
        referrer: Referring URL if available
        user_agent: Browser/client user agent string
        timestamp: When the visit occurred
    """
    __tablename__ = 'site_visit'

    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45))
    path = db.Column(db.String(500))
    referrer = db.Column(db.String(500))
    user_agent = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime(timezone=True), default=func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'ip_address': self.ip_address,
            'path': self.path,
            'referrer': self.referrer,
            'user_agent': self.user_agent,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }

    def __repr__(self):
        return f'<SiteVisit {self.id} - {self.path}>'


# ============================================================================
# GEO IP CACHE MODEL
# ============================================================================
class GeoIPCache(db.Model):
    """
    Caches GeoIP lookup results to avoid repeated API calls.

    Attributes:
        id: Primary key
        ip_address: The looked-up IP (unique)
        country: Country name or code
        region: Region/state
        city: City name
        isp: Internet service provider
        cached_at: When this record was cached
    """
    __tablename__ = 'geo_ip_cache'

    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), unique=True, nullable=False)
    country = db.Column(db.String(100))
    region = db.Column(db.String(100))
    city = db.Column(db.String(100))
    isp = db.Column(db.String(200))
    cached_at = db.Column(db.DateTime(timezone=True), default=func.now())

    def to_dict(self):
        return {
            'ip_address': self.ip_address,
            'country': self.country,
            'region': self.region,
            'city': self.city,
            'isp': self.isp,
        }

    def __repr__(self):
        return f'<GeoIPCache {self.ip_address} - {self.country}>'


# ============================================================================
# ADMIN AUDIT LOG MODEL
# ============================================================================
class AdminAuditLog(db.Model):
    """
    Records admin actions for audit trail purposes.

    Attributes:
        id: Primary key
        action: The action performed (e.g. 'user.create', 'ban.ip')
        target_type: The type of entity acted upon (e.g. 'user', 'ip')
        target_id: The ID of the entity acted upon
        details: Additional details about the action (JSON or text)
        admin_ip: IP address of the admin who performed the action
        timestamp: When the action occurred
    """
    __tablename__ = 'admin_audit_log'

    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.String(50))
    details = db.Column(db.Text)
    admin_ip = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime(timezone=True), default=func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'action': self.action,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'details': self.details,
            'admin_ip': self.admin_ip,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }

    def __repr__(self):
        return f'<AdminAuditLog {self.id} - {self.action}>'


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

    def to_dict(self, include_purchases=False):
        d = {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'creation_date': self.creation_date.isoformat() if self.creation_date else None,
        }
        if include_purchases:
            d['purchases'] = [p.to_dict() for p in self.buys] if self.buys else []
        return d

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

    def to_dict(self):
        return {
            'id': self.id,
            'product_name': self.product_name,
            'city': self.city,
            'country': self.country,
            'line1': self.line1,
            'line2': self.line2,
            'postal_code': self.postal_code,
            'state': self.state,
            'pay_status': self.pay_status,
            'purchase_date': self.purchase_date.isoformat() if self.purchase_date else None,
            'customer_id': self.customer_id,
        }

    def __repr__(self):
        return f'<Purchase {self.id} - {self.product_name}>'
