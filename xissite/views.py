"""
Public Views Routes
===================

This module handles public-facing pages:
- Home page
- About page
- Contact/Feedback form
- Sell page (product listing)

No authentication required for these routes.
"""

from flask import Blueprint, render_template, flash, request
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import (TextAreaField, SubmitField, RadioField, StringField,
                     IntegerField, HiddenField)
from wtforms.validators import DataRequired, Length, InputRequired, Email, Optional

from . import db
from .models import FeedBack
from .spam_guard import validate_submission, generate_timestamp_token, contact_rate_limiter

# Initialize CSRF protection
csrf = CSRFProtect()

# Create Blueprint
views = Blueprint('views', __name__)


# ============================================================================
# FORMS
# ============================================================================

class ContactForm(FlaskForm):
    """
    Customer feedback/contact form.
    
    Fields:
        feedbackemail: Customer's email for response
        feedbacktype: Type of feedback (General or Order-related)
        orderno: Optional order ID for order-specific feedback
        feedbackfield: The actual feedback message
    """
    feedbackemail = StringField(
        'Email', 
        validators=[
            DataRequired(message="Email is required"),
            Length(min=1, max=100),
            Email(message="Please enter a valid email address")
        ]
    )
    feedbacktype = RadioField(
        'Type of Feedback',
        choices=[
            ('General', 'General Inquiry'),
            ('Technical', 'Technical Support'),
            ('Order', 'Order Related'),
            ('Feature', 'Feature Request'),
        ],
        validators=[InputRequired(message="Please select a feedback type")]
    )
    orderno = StringField(
        'Order Number',
        validators=[Optional(), Length(max=50)]
    )
    serialno = StringField(
        'Serial Number',
        validators=[Optional(), Length(max=100)]
    )
    feedbackfield = TextAreaField(
        'Leave Feedback', 
        validators=[
            DataRequired(message="Please enter your feedback"),
            Length(min=10, max=2000, message="Feedback must be between 10 and 2000 characters")
        ]
    )
    submit = SubmitField('Submit Feedback')

    # Anti-spam fields (not visible to users)
    website = StringField('Website', validators=[Optional()])  # Honeypot
    form_loaded_at = HiddenField()  # Timestamp token


# ============================================================================
# PUBLIC ROUTES
# ============================================================================

@views.route('/')
def home():
    """Home page - main landing page."""
    return render_template("home.html")


@views.route('/about')
def about():
    """About page - company information."""
    return render_template("about.html")


@views.route('/sell')
@csrf.exempt
def sale():
    """
    Product sales page.
    
    Note: CSRF exempt as this page just displays product info.
    The actual checkout is handled by Stripe.
    """
    return render_template("sell.html")


@views.route('/contact', methods=['GET', 'POST'])
def contact():
    """
    Contact/Feedback page with layered anti-spam protection.

    GET: Display the feedback form with anti-spam tokens
    POST: Validate against spam checks, then store if clean

    Anti-spam layers:
        1. Honeypot field (hidden from real users)
        2. Time-based validation (rejects instant submissions)
        3. Rate limiting per IP (max 3/hour)
        4. Email domain blocklist (disposable emails)
        5. URL/link detection in message content
        6. Suspicious content scoring
    """
    csrf.protect()
    form = ContactForm()
    message_type = ''  # 'success' or 'error' for styling

    if request.method == 'GET':
        from flask import current_app
        form.form_loaded_at.data = generate_timestamp_token(
            current_app.config['SECRET_KEY']
        )

    if request.method == 'POST':
        if form.validate_on_submit():
            from flask import current_app

            # Get client IP (App Engine uses X-Forwarded-For)
            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            if client_ip and ',' in client_ip:
                client_ip = client_ip.split(',')[0].strip()

            # Run anti-spam checks
            spam_result = validate_submission(
                form_data=request.form,
                email=form.feedbackemail.data,
                message=form.feedbackfield.data,
                timestamp_token=request.form.get('form_loaded_at', ''),
                secret_key=current_app.config['SECRET_KEY'],
                ip_address=client_ip,
            )

            if spam_result['is_spam']:
                failed_str = '; '.join(
                    f"{name}: {reason}"
                    for name, reason, score in spam_result['failed_checks']
                )
                print(f"[SPAM BLOCKED] IP={client_ip} email={form.feedbackemail.data} "
                      f"score={spam_result['total_score']} checks=[{failed_str}]")

                if spam_result['is_silent_reject']:
                    flash(spam_result['rejection_message'], 'success')
                    message_type = 'success'
                    form = ContactForm(formdata=None)
                else:
                    flash(spam_result['rejection_message'], 'error')
                    message_type = 'error'

                return render_template("contact.html", form=form, message_type=message_type)

            # Passed all checks: record rate limit and save
            contact_rate_limiter.record(client_ip)

            try:
                new_feedback = FeedBack(
                    feedbackmail=form.feedbackemail.data,
                    feedbacktype=form.feedbacktype.data,
                    feedbackorderid=form.orderno.data if form.orderno.data else None,
                    feedbackfullfield=form.feedbackfield.data,
                    submitter_ip=client_ip,
                    serial_number=form.serialno.data if form.serialno.data else None,
                )

                db.session.add(new_feedback)
                db.session.commit()

                print(f"[FEEDBACK] New submission from {form.feedbackemail.data}")
                flash('Thank you! Your feedback has been submitted successfully.', 'success')
                message_type = 'success'

                # Clear form after successful submission
                form = ContactForm(formdata=None)

            except Exception as e:
                db.session.rollback()
                print(f"[ERROR] Failed to save feedback: {str(e)}")
                flash('An error occurred. Please try again.', 'error')
                message_type = 'error'
        else:
            print(f"[FEEDBACK] Validation failed: {form.errors}")
            flash('Please check your information and try again.', 'error')
            message_type = 'error'

    return render_template("contact.html", form=form, message_type=message_type)
