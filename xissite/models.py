from flask_login import UserMixin
from stripe import PaymentIntent
from . import db
from .constants import utherr, pahwur
from sqlalchemy.sql import func
import datetime

current_product = "Hydroponics System V1"

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable = False)
    name = db.Column(db.String(150), nullable = False)
    creation_date = db.Column(db.DateTime(timezone=True), default=func.current_timestamp()) 
    notes_on_customer = db.Column(db.String(500), nullable = True)
    buys = db.relationship('Purchase_info', backref='customer')


class Purchase_info(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'))
    
    product_name = db.Column(db.String(20), default = current_product)
    purchase_date = db.Column(db.DateTime(timezone=True), default=func.now())

    city = db.Column(db.String(500), nullable = False)
    country = db.Column(db.String(500), nullable = False)
    line1 = db.Column(db.String(500), nullable = False)
    line2 = db.Column(db.String(500), nullable = True)
    postal_code = db.Column(db.Integer, nullable = False)
    state = db.Column(db.String(500), nullable = False)

    pay_status = db.Column(db.String(50), default='Awaiting Payment')


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key = True)
    user_name = db.Column(db.String(150), default = utherr)
    pass_word = db.Column(db.String(150), default = pahwur)