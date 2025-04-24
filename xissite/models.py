from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func
import os
from dotenv import load_dotenv

# Try to load environment variables from vars.env
if os.path.exists('vars.env'):
    load_dotenv('vars.env')

# Configuration
admin_username = os.environ.get('ADMIN_USERNAME_HASH')
admin_password = os.environ.get('ADMIN_PASSWORD_HASH')
current_product = "HydroGardenMaxSomething 2000"

class FeedBack(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150))
    subject = db.Column(db.String(150))
    content = db.Column(db.String(10000))
    date = db.Column(db.DateTime(timezone=True), default=func.now())
    
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), nullable=False)
    name = db.Column(db.String(150))
    purchase = db.relationship('Purchase_info')

class Purchase_info(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(150))
    country = db.Column(db.String(150))
    line1 = db.Column(db.String(150))
    line2 = db.Column(db.String(150))
    postal_code = db.Column(db.String(150))
    state = db.Column(db.String(150))
    pay_status = db.Column(db.String(150))
    date = db.Column(db.DateTime(timezone=True), default=func.now())
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'))
    customer = db.relationship('Customer')