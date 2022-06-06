from flask import Blueprint, Flask, redirect, render_template, request, jsonify
import os
import stripe
from werkzeug.security import generate_password_hash, check_password_hash
from . import db

from .models import Customer, Purchase_info
from .constants import STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, HP_Price_id, endpoint_secret

sales = Blueprint('sales', __name__)

stripe.api_key = STRIPE_SECRET_KEY

YOUR_DOMAIN = 'http://localhost:5000'

@sales.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        checkout_session = stripe.checkout.Session.create(
        shipping_address_collection={
            'allowed_countries': ['US', 'CA'],
        },
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


#WEBHOOKS ----------------
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
    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']

        # Save an order in your database, marked as 'awaiting payment'
        create_order(session)

        # Check if the order is already paid (for example, from a card payment)
        #
        # A delayed notification payment will have an `unpaid` status, as
        # you're still waiting for funds to be transferred from the customer's
        # account.
        if session.payment_status == "paid":
        # Fulfill the purchase
            print("Payment is Paid...n stuff.")
            fulfill_order(session)

    elif event['type'] == 'checkout.session.async_payment_succeeded':
        session = event['data']['object']

        # Fulfill the purchase
    
        fulfill_order(session)

    elif event['type'] == 'checkout.session.async_payment_failed':
        session = event['data']['object']

        # Send an email to the customer asking them to retry their order
        email_customer_about_failed_payment(session)


    return jsonify(success=True)

def fulfill_order(session):
  # TODO: fill me in
  print("Fulfilling order")




def create_order(session):
    
    customer_email = session["customer_details"]["email"]
    customer_name = session["customer_details"]["name"]

    #Make collecting shipping info easier
    customer_ship_address = session["customer_details"]["address"]

    #Breaking down shipping address dictionary object for easier appending to database... I know it looks rough but its quick, dirty and easier
    c_city = customer_ship_address["city"]
    c_country = customer_ship_address["country"]
    c_line1 = customer_ship_address["line1"]
    c_line2 = customer_ship_address["line2"]
    c_postal = int(customer_ship_address["postal_code"])
    c_state = customer_ship_address["state"]
 
    paym_status = session["payment_status"]

    #Check if customer already has made a purchase on site before
    #If so, add purchase to existing customer entry
    if Customer.query.filter(Customer.email == customer_email).first():
        print("Pre-existing Customer/Buyer. Skipping Initial Customer Creation.\n")
        
        existing_customer = db.session.query(Customer).filter_by(email = customer_email).first()
        newly_purchase = Purchase_info(city = c_city, country = c_country, line1 = c_line1, line2 = c_line2, postal_code = c_postal, state = c_state, pay_status = paym_status, customer = existing_customer)
        db.session.add(newly_purchase)
        db.session.commit()

        print("New Purchase Added To Customer\n")

    #If Customer has not made a purchase before (at least with email used to checkout) and is not in db, create new customer with purchase child 
    else:
        newly_customer = Purchase_info(city = c_city, country = c_country, line1 = c_line1, line2 = c_line2, postal_code = c_postal, state = c_state, pay_status = paym_status, customer = Customer(email = customer_email, name = customer_name))
        db.session.add(newly_customer)
        db.session.commit()
        db.session.add(newly_customer)
        db.session.commit()
        print("Creating order for new customer")
        
        

    

def email_customer_about_failed_payment(session):
  # TODO: fill me in
    print("Emailing customer")
