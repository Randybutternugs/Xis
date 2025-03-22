from operator import contains
from xmlrpc.client import boolean
from flask import Blueprint, Flask, redirect, url_for, render_template, request, jsonify, flash
from sqlalchemy.sql import func
import os
import stripe
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Length
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv

# Try to load environment variables from vars.env
if os.path.exists('vars.env'):
    load_dotenv('vars.env')

# Default values if environment variables aren't set
DEFAULT_STRIPE_SECRET_KEY = 'sk_test_51KyKprGjhGCkZIA1cVsqA0wQCz7gLnYSI9dgnkicu3ZiLlkR5fmsi9IbuObb30tIogXR1qSN3Gyae9ttlcmwc2VQ00oqXnbACF'
DEFAULT_STRIPE_PUBLISHABLE_KEY = 'pk_test_51KyKprGjhGCkZIA1kWujqcDZSVbZfQV4K9jdKzt6f4ynhdD77Befi1VuERMLw9JOZLsu4MCLaHiHvbYYONjNsvZa00HHxE631y'
DEFAULT_HP_PRICE_ID = 'price_1KyMGfGjhGCkZIA1EHcmGKe8'
DEFAULT_ENDPOINT_SECRET = 'whsec_fae63b8434767512665c47f0455bfb9812e5ca696a91bb394edfad39a6e81385'
DEFAULT_USERHASH = 'pbkdf2:sha256:260000$Eqv0Pi1vv3Q6g5dg$ae6edc01736b9e0f99e633e67e1dfdcacfe74ddbaa345e2880d02a8411a91250'
DEFAULT_PASSHASH = 'pbkdf2:sha256:260000$iCuXV4wOpxZ6mdLK$7630e538a1075973640d2d2869f3b7b437d934f8fb30f1f4bd792fb65b76be15'

# Get values from environment variables or use defaults
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', DEFAULT_STRIPE_SECRET_KEY)
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', DEFAULT_STRIPE_PUBLISHABLE_KEY)
HP_Price_id = os.environ.get('HP_PRICE_ID', DEFAULT_HP_PRICE_ID)
endpoint_secret = os.environ.get('STRIPE_WEBHOOK_SECRET', DEFAULT_ENDPOINT_SECRET)
utherr = os.environ.get('ADMIN_USERNAME_HASH', DEFAULT_USERHASH)
pahwur = os.environ.get('ADMIN_PASSWORD_HASH', DEFAULT_PASSHASH)

csrf = CSRFProtect()

from . import db

from .models import Customer, FeedBack, Purchase_info, User, FeedBack

# Form classes
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class SearchForm(FlaskForm):
    SearchWord = StringField('', validators=[DataRequired(), Length(min=1, max=40)])
    submit = SubmitField('')

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET','POST'])       
def login():
    csrf.protect()
    form = LoginForm()  # Create form instance

    if request.method == 'GET':
        admencheck = db.session.query(User).first()
        if admencheck == None:
            newmin = User(user_name="randy", pass_word="Hello")
            db.session.add(newmin)
            db.session.commit()
            print('\n \n \n Newmin Created \n \n \n')
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        usernamechk = check_password_hash(utherr, username)
        passwordchk = check_password_hash(pahwur, password)

        if usernamechk and passwordchk:
            uszur = User.query.get(1)
            login_user(uszur, remember=True)
            return redirect(url_for('auth.viewdatabase'))
        else:
            print("\n \n INVALID LOGIN DETECTED...\n \n")
            flash('Invalid login credentials', 'error')

    return render_template('loginpage.html', form=form, boolean=True)  # Pass form to template

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

#DATABASE VIEWER ------
@auth.route('/viewdb', methods=['GET','POST'])
@login_required
def viewdatabase():
    customerinf = Customer.query.order_by(Customer.id)
    form = SearchForm() 
    
    if form.validate_on_submit():
        if "@" in form.SearchWord.data:
            try:
                foundid = db.session.query(Customer.id).filter_by(email=form.SearchWord.data).first()[0]
                return redirect('/viewdb/' + str(foundid))
            except Exception as e:
                flash(u'Email Not Found')
        else:
            try:
                foundid = db.session.query(Purchase_info.customer_id).filter_by(id=form.SearchWord.data).first()[0]
                return redirect('/viewdb/' + str(foundid))
            except Exception as e:
                flash(u'Purchase ID Not Found')
                
    return render_template('show.html', customerinf=customerinf, form=form)

@auth.route('/viewdb/<int:customerid>', methods=['GET'])
@login_required
def viewcustomer(customerid):
    customer_info = Customer.query.get(customerid)
    customer_purchasesno = db.session.query(Customer.id, func.count(Customer.id)).join(Customer.buys).filter_by(customer_id=customer_info.id).first()[1]
    customer_purchase_info = db.session.query(Purchase_info).filter_by(customer_id=customer_info.id).all()
    return render_template('showmore.html', customer_info=customer_info, customer_purchase_info=customer_purchase_info, customer_purchasesno=customer_purchasesno)

@auth.route('/viewdb/feedbackview', methods=['GET'])
@login_required
def viewfeedback():
    feedback_info = FeedBack.query.order_by(FeedBack.id)
    return render_template('feedbackview.html', feedback_info=feedback_info)