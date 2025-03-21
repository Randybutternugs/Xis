from flask_login import UserMixin
from . import db
from sqlalchemy.sql import func
import datetime
import os
from dotenv import load_dotenv

# Try to load environment variables from vars.env
if os.path.exists('vars.env'):
    load_dotenv('vars.env')

# Default values if environment variables aren't set
DEFAULT_USERHASH = 'pbkdf2:sha256:260000$Eqv0Pi1vv3Q6g5dg$ae6edc01736b9e0f99e633e67e1dfdcacfe74ddbaa345e2880d02a8411a91250'
DEFAULT_PASSHASH = 'pbkdf2:sha256:260000$iCuXV4wOpxZ6mdLK$7630e538a1075973640d2d2869f3b7b437d934f8fb30f1f4bd792fb65b76be15'

# Get values from environment variables or use defaults
admin_username = os.environ.get('ADMIN_USERNAME_HASH', DEFAULT_USERHASH)
admin_password = os.environ.get('ADMIN_PASSWORD_HASH', DEFAULT_PASSHASH)

current_product = "Hydroponics System V1"

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    creation_date = db.Column(db.DateTime(timezone=True), default=func.current_timestamp()) 
    notes_on_customer = db.Column(db.String(500), nullable=True)
    buys = db.relationship('Purchase_info', backref='customer')


class Purchase_info(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'))
    product_name = db.Column(db.String(20), default=current_product)
    purchase_date = db.Column(db.DateTime(timezone=True), default=func.now())

    city = db.Column(db.String(500), nullable=False)
    country = db.Column(db.String(500), nullable=False)
    line1 = db.Column(db.String(500), nullable=False)
    line2 = db.Column(db.String(500), nullable=True)
    postal_code = db.Column(db.String(500), nullable=False)
    state = db.Column(db.String(500), nullable=False)

    pay_status = db.Column(db.String(50), default='Awaiting Payment')


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(150), default=admin_username)
    pass_word = db.Column(db.String(150), default=admin_password)


class FeedBack(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    feedbackmail = db.Column(db.String(40), nullable=False)
    feedbacktype = db.Column(db.Integer, nullable=False)
    feedbackorderid = db.Column(db.Integer, nullable=True)
    feedbackfullfield = db.Column(db.String(600), nullable=False)
    date = db.Column(db.DateTime(timezone=True), default=func.now())