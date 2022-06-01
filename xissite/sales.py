from flask import Blueprint, Flask, redirect, render_template, request, jsonify
import os
import stripe
from werkzeug.security import generate_password_hash, check_password_hash
from . import db

from .models import Customer
from .constants import STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, HP_Price_id, endpoint_secret

sales = Blueprint('sales', __name__)

stripe.api_key = STRIPE_SECRET_KEY

YOUR_DOMAIN = 'http://localhost:5000'

@sales.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
                    'price': HP_Price_id,
                    'quantity': 1,
                },
            ],
            mode='payment',
            success_url=YOUR_DOMAIN + '/success',
            cancel_url=YOUR_DOMAIN + '/cancel',
            automatic_tax={'enabled': True},
        )
    except Exception as e:
        return str(e)

    return redirect(checkout_session.url, code=303)

@sales.route('/success')
def successfulpurchase():
    return render_template('success.html')

@sales.route('/cancel')
def cancel():
    return render_template('cancel.html')

#DATABASE VIEWER ------
@sales.route('/viewdb', methods=['POST','GET'])
def viewdatabase():
    customerinf = Customer.query.order_by(Customer.id)
    return render_template('show.html', customerinf=customerinf)


#WEBHOOKS
@sales.route('/webhook', methods=['POST', 'GET'])
def webhook():
    event = None
    payload = request.data
    sig_header = request.headers['STRIPE_SIGNATURE']

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        raise e
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise e

    # Handle the event
    #print('Unhandled event type {}'.format(event['type']))

    if event['type'] == 'checkout.session.completed':
        sesh = event['data']['object']
        customer_email = sesh["customer_details"]["email"]
        customer_name = sesh["customer_details"]["name"]
        payment_intent = sesh["payment_intent"]
        print(type(customer_email))
        newly_customer = Customer(email = customer_email, name = customer_name)
        db.session.add(newly_customer)
        db.session.commit()
        #print(session)
        #print(customer_name)
        #print(customer_email)
        print("NEW CUSTOMER CREATED.")
        #  - send an email to the customer
    else:
        print(event)
        print('CUSTOMER ADD FAILED')


    return jsonify(success=True)
