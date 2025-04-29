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

#os.environ['ADMIN_USERNAME_HASH'] = 'scrypt:32768:8:1$RkmSaBoEJHHEOrob$a436468c6580b68f67c3fdd733a7c52c38da768ee6dd9414da8dbdafa78ae5f92e0793fc613a78a9cd6ea5312abd5d23faf868eb0e0d2e1f52a06d1164547718'
#os.environ['ADMIN_PASSWORD_HASH'] = 'scrypt:32768:8:1$zOlfRPNfqJrkzdpu$94f1b0d718e1e0363f1fe709065c9d4b229819b03bb9e85c6bb61dc9f2737435e2dca08331f37a08fe2e9c70f68f0018a3a9ebb97e06d1e2f91363def8c535f6'
#os.environ['DEFAULT_USERHASH'] = 'scrypt:32768:8:1$RkmSaBoEJHHEOrob$a436468c6580b68f67c3fdd733a7c52c38da768ee6dd9414da8dbdafa78ae5f92e0793fc613a78a9cd6ea5312abd5d23faf868eb0e0d2e1f52a06d1164547718'
#os.environ['DEFAULT_PASSHASH'] = 'scrypt:32768:8:1$zOlfRPNfqJrkzdpu$94f1b0d718e1e0363f1fe709065c9d4b229819b03bb9e85c6bb61dc9f2737435e2dca08331f37a08fe2e9c70f68f0018a3a9ebb97e06d1e2f91363def8c535f6'

# Get values from environment variables
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
HP_PRICE_ID = os.environ.get('HP_PRICE_ID')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
ADMIN_USERNAME_HASH = os.environ.get('ADMIN_USERNAME_HASH')
ADMIN_PASSWORD_HASH = os.environ.get('ADMIN_PASSWORD_HASH')
DEFAULT_USERHASH = os.environ.get('DEFAULT_USERHASH')
DEFAULT_PASSHASH = os.environ.get('DEFAULT_PASSHASH')

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
            newmin = User(email=ADMIN_USERNAME_HASH, password=ADMIN_PASSWORD_HASH)
            db.session.add(newmin)
            db.session.commit()
            print('\n \n \n Newmin Created \n \n \n')
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        print("\n \n \n HELLO THIS IS THE HASH NEXT: ")
        print(ADMIN_USERNAME_HASH)

        usernamechk = check_password_hash(ADMIN_USERNAME_HASH, username)
        passwordchk = check_password_hash(ADMIN_PASSWORD_HASH, password)

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