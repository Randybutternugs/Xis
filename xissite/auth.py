from xmlrpc.client import boolean
from flask import Blueprint, Flask, redirect, url_for, render_template, request, jsonify
from sqlalchemy.sql import func
import os
import stripe
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user

from . import db

from .models import Customer, Purchase_info, User
from .constants import STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, HP_Price_id, endpoint_secret, utherr, pahwur

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET','POST'])
def login():


    if request.method == 'GET':
        admencheck = db.session.query(User).first()
        if admencheck == None:
            newmin = User(user_name = None, pass_word = None)
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

    return render_template('loginpage.html', boolean=True)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

#DATABASE VIEWER ------
@auth.route('/viewdb', methods=['GET'])
@login_required
def viewdatabase():
    customerinf = Customer.query.order_by(Customer.id)
    return render_template('show.html', customerinf=customerinf)

@auth.route('/viewdb/<int:customerid>', methods=['GET'])
@login_required
def viewcustomer(customerid):
    customer_info = Customer.query.get(customerid)
    #Big one lol, queries Customer purchases using customer id as x value and number of purchase objects as y, returns (x,y), use [] to only grab item in index 1 of coordinate pair :D
    customer_purchasesno = db.session.query(Customer.id, func.count(Customer.id)).join(Customer.buys).filter_by(customer_id = customer_info.id).first()[1]
    #Pulls all purchases for customer id from database, can be iterated through using Jinga on relevant database viewer html doc
    customer_purchase_info = db.session.query(Purchase_info).filter_by(customer_id = customer_info.id).all()
    return render_template('showmore.html', customer_info = customer_info, customer_purchase_info = customer_purchase_info, customer_purchasesno = customer_purchasesno)