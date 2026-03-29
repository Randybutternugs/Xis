"""
Sales & Stripe Integration Routes
=================================

This module handles:
- Stripe checkout session creation
- Payment success/cancel pages
- Stripe webhook processing for order fulfillment
- Customer/purchase database updates
- Order confirmation emails via Postmark

Environment Variables Required:
    STRIPE_SECRET_KEY: Stripe API secret key
    STRIPE_WEBHOOK_SECRET: Stripe webhook signing secret
    HP_PRICE_ID: Stripe Price ID for the product
    POSTMARK_SERVER_TOKEN: Postmark API server token
    POSTMARK_SENDER_EMAIL: Verified sender email for Postmark

Deployment Note:
    Update MAIN_DOMAIN before deploying to production.
    For Google Cloud, this would be your App Engine URL.
"""

from flask import Blueprint, redirect, render_template, request, jsonify
import requests
import os
import stripe
from flask_wtf.csrf import CSRFProtect

from . import db
from .models import Customer, Purchase_info

# Initialize
csrf = CSRFProtect()
sales = Blueprint('sales', __name__)

# Configure Stripe
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

# ============================================================================
# CONFIGURATION
# ============================================================================

# IMPORTANT: Update this to your production domain before deploying
# For Google Cloud App Engine, this would be: https://your-project-id.appspot.com
# For local development: http://localhost:5000
MAIN_DOMAIN = os.environ.get('MAIN_DOMAIN', 'http://localhost:5000')

# Current product being sold
CURRENT_PRODUCT = "Tull Tower V1"

# Shipping countries allowed
ALLOWED_SHIPPING_COUNTRIES = ['US', 'CA']


# ============================================================================
# CHECKOUT ROUTES
# ============================================================================

@sales.route('/create-checkout-session', methods=['POST'])
@csrf.exempt
def create_checkout_session():
    """
    Create a Stripe Checkout Session for product purchase.
    
    Redirects customer to Stripe's hosted checkout page.
    On completion, customer is redirected to success or cancel URL.
    
    Returns:
        Redirect to Stripe Checkout or error message
    """
    # Validate Stripe configuration
    price_id = os.environ.get('HP_PRICE_ID')
    if not price_id:
        print("[ERROR] HP_PRICE_ID not configured")
        return "Payment system not configured. Please contact support.", 500
    
    if not stripe.api_key:
        print("[ERROR] STRIPE_SECRET_KEY not configured")
        return "Payment system not configured. Please contact support.", 500
    
    try:
        checkout_session = stripe.checkout.Session.create(
            shipping_address_collection={
                'allowed_countries': ALLOWED_SHIPPING_COUNTRIES,
            },
            line_items=[
                {
                    'price': price_id,
                    'quantity': 1,
                },
            ],
            mode='payment',
            success_url=f'{MAIN_DOMAIN}/success',
            cancel_url=f'{MAIN_DOMAIN}/cancel',
            automatic_tax={'enabled': True},
        )
        
        print(f"[STRIPE] Checkout session created: {checkout_session.id}")
        return redirect(checkout_session.url, code=303)
        
    except stripe.error.StripeError as e:
        print(f"[STRIPE ERROR] {str(e)}")
        return f"Payment error: {str(e)}", 400
    except Exception as e:
        print(f"[ERROR] Checkout session creation failed: {str(e)}")
        return "An error occurred. Please try again.", 500


@sales.route('/success')
def successfulpurchase():
    """Display success page after completed purchase."""
    return render_template('success.html')


@sales.route('/cancel')
def cancel():
    """Display cancellation page when customer abandons checkout."""
    return render_template('cancel.html')


# ============================================================================
# STRIPE WEBHOOKS
# ============================================================================

@sales.route('/webhook', methods=['POST'])
@csrf.exempt
def webhook():
    """
    Stripe Webhook Handler.
    
    Processes events from Stripe to:
    - Create order records when checkout completes
    - Fulfill orders when payment is confirmed
    - Handle async payment failures
    
    Webhook Events Handled:
        - checkout.session.completed: Create order, fulfill if paid
        - checkout.session.async_payment_succeeded: Fulfill delayed payment
        - checkout.session.async_payment_failed: Notify customer
    
    Returns:
        JSON response with success status
    """
    payload = request.data
    sig_header = request.headers.get('STRIPE_SIGNATURE')
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
    
    if not webhook_secret:
        print("[ERROR] STRIPE_WEBHOOK_SECRET not configured")
        return jsonify(error="Webhook not configured"), 500
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        print(f"[WEBHOOK ERROR] Invalid payload: {str(e)}")
        return jsonify(error="Invalid payload"), 400
    except stripe.error.SignatureVerificationError as e:
        print(f"[WEBHOOK ERROR] Invalid signature: {str(e)}")
        return jsonify(error="Invalid signature"), 400

    # Handle specific event types
    event_type = event['type']
    print(f"[WEBHOOK] Received event: {event_type}")
    
    if event_type == 'checkout.session.completed':
        session = event['data']['object']
        
        # Create order record
        create_order(session)
        
        # If already paid (card payment), fulfill immediately
        if session.payment_status == "paid":
            print("[WEBHOOK] Payment confirmed, fulfilling order")
            fulfill_order(session)

    elif event_type == 'checkout.session.async_payment_succeeded':
        session = event['data']['object']
        print("[WEBHOOK] Async payment succeeded, fulfilling order")
        fulfill_order(session)

    elif event_type == 'checkout.session.async_payment_failed':
        session = event['data']['object']
        print("[WEBHOOK] Async payment failed, notifying customer")
        email_customer_about_failed_payment(session)

    return jsonify(success=True)


# ============================================================================
# ORDER PROCESSING FUNCTIONS
# ============================================================================

def create_order(session):
    """
    Create or update customer and purchase records from Stripe session.
    
    If customer email already exists, adds purchase to existing customer.
    Otherwise, creates new customer record with purchase.
    
    Args:
        session: Stripe checkout session object
    """
    try:
        customer_email = session["customer_details"]["email"]
        customer_name = session["customer_details"]["name"]
        customer_ship_address = session["customer_details"]["address"]
        payment_status = session["payment_status"]
        
        # Extract address components
        address_data = {
            'city': customer_ship_address.get("city"),
            'country': customer_ship_address.get("country"),
            'line1': customer_ship_address.get("line1"),
            'line2': customer_ship_address.get("line2"),
            'postal_code': customer_ship_address.get("postal_code"),
            'state': customer_ship_address.get("state"),
        }
        
        # Check if customer already exists
        existing_customer = Customer.query.filter_by(email=customer_email).first()
        
        if existing_customer:
            # Add purchase to existing customer
            print(f"[ORDER] Adding purchase to existing customer: {customer_email}")
            new_purchase = Purchase_info(
                product_name=CURRENT_PRODUCT,
                pay_status=payment_status,
                customer_id=existing_customer.id,
                **address_data
            )
            db.session.add(new_purchase)
        else:
            # Create new customer with purchase
            print(f"[ORDER] Creating new customer: {customer_email}")
            new_customer = Customer(
                email=customer_email,
                name=customer_name
            )
            db.session.add(new_customer)
            db.session.flush()  # Get the customer ID
            
            new_purchase = Purchase_info(
                product_name=CURRENT_PRODUCT,
                pay_status=payment_status,
                customer_id=new_customer.id,
                **address_data
            )
            db.session.add(new_purchase)
        
        db.session.commit()
        print(f"[ORDER] Order created successfully for {customer_email}")
        
    except Exception as e:
        db.session.rollback()
        print(f"[ORDER ERROR] Failed to create order: {str(e)}")
        raise


def fulfill_order(session):
    """
    Fulfill order by sending confirmation email via Postmark.

    Args:
        session: Stripe checkout session object
    """
    customer_email = session["customer_details"]["email"]
    customer_name = session["customer_details"]["name"]

    server_token = os.environ.get('POSTMARK_SERVER_TOKEN')
    sender_email = os.environ.get('POSTMARK_SENDER_EMAIL')
    if not server_token or not sender_email:
        print("[FULFILL WARNING] Postmark not configured, skipping email")
        return

    print(f"[FULFILL] Sending confirmation to {customer_email}")

    try:
        from .email_templates import order_confirmation_html
        response = requests.post(
            'https://api.postmarkapp.com/email',
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-Postmark-Server-Token': server_token,
            },
            json={
                'From': sender_email,
                'To': customer_email,
                'Subject': 'Order Confirmation - Tull Hydroponics',
                'HtmlBody': order_confirmation_html(customer_name, CURRENT_PRODUCT, '$200'),
            },
        )

        if response.status_code == 200:
            print(f"[FULFILL] Email sent successfully to {customer_email}")
        else:
            print(f"[FULFILL WARNING] Email failed: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"[FULFILL ERROR] Failed to send email: {str(e)}")


def email_customer_about_failed_payment(session):
    """
    Notify customer about failed payment via Postmark.

    Args:
        session: Stripe checkout session object
    """
    customer_email = session["customer_details"]["email"]
    customer_name = session["customer_details"]["name"]

    server_token = os.environ.get('POSTMARK_SERVER_TOKEN')
    sender_email = os.environ.get('POSTMARK_SENDER_EMAIL')
    if not server_token or not sender_email:
        print("[EMAIL WARNING] Postmark not configured, skipping email")
        return

    print(f"[EMAIL] Sending payment failure notice to {customer_email}")

    try:
        from .email_templates import payment_failed_html
        response = requests.post(
            'https://api.postmarkapp.com/email',
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-Postmark-Server-Token': server_token,
            },
            json={
                'From': sender_email,
                'To': customer_email,
                'Subject': 'Payment Failed - Tull Hydroponics',
                'HtmlBody': payment_failed_html(customer_name),
            },
        )

        if response.status_code == 200:
            print(f"[EMAIL] Payment failure notice sent to {customer_email}")
        else:
            print(f"[EMAIL WARNING] Failed to send notice: {response.status_code}")

    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send payment failure notice: {str(e)}")
