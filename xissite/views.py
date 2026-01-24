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
from wtforms import TextAreaField, SubmitField, RadioField, StringField, IntegerField
from wtforms.validators import DataRequired, Length, InputRequired, Email, Optional

from . import db
from .models import FeedBack

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
            ('General', 'General Feedback'),
            ('Order', 'Order Feedback')
        ], 
        validators=[InputRequired(message="Please select a feedback type")]
    )
    orderno = StringField(
        'Order Number', 
        validators=[Optional(), Length(max=50)]
    )
    feedbackfield = TextAreaField(
        'Leave Feedback', 
        validators=[
            DataRequired(message="Please enter your feedback"),
            Length(min=10, max=2000, message="Feedback must be between 10 and 2000 characters")
        ]
    )
    submit = SubmitField('Submit Feedback')


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
    Contact/Feedback page.
    
    GET: Display the feedback form
    POST: Process and store feedback submission
    
    Flash messages indicate success or error status.
    """
    csrf.protect()
    form = ContactForm()
    message_type = ''  # 'success' or 'error' for styling
    
    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                # Create new feedback record
                new_feedback = FeedBack(
                    feedbackmail=form.feedbackemail.data,
                    feedbacktype=form.feedbacktype.data,
                    feedbackorderid=form.orderno.data if form.orderno.data else None,
                    feedbackfullfield=form.feedbackfield.data
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
            # Form validation failed
            print(f"[FEEDBACK] Validation failed: {form.errors}")
            flash('Please check your information and try again.', 'error')
            message_type = 'error'
    
    return render_template("contact.html", form=form, message_type=message_type)
