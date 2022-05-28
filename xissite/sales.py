from flask import Blueprint, Flask, redirect, render_template, request
import os
import stripe

sales = Blueprint('sales', __name__)

stripe.api_key = 'sk_test_51KyKprGjhGCkZIA1cVsqA0wQCz7gLnYSI9dgnkicu3ZiLlkR5fmsi9IbuObb30tIogXR1qSN3Gyae9ttlcmwc2VQ00oqXnbACF'

YOUR_DOMAIN = 'http://localhost:5000'

@sales.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
                    'price': 'price_1KyMGfGjhGCkZIA1EHcmGKe8',
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
