from stripe import PaymentIntent
from . import db
from sqlalchemy.sql import func
import datetime

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    name = db.Column(db.String(150))
    date = db.Column(db.DateTime(timezone=True), default=func.current_timestamp()) #REMOVE LATER
    #buys = db.relationship('purchase_info')


#    class purchase_info(db.Model):
 #       id = db.Column(db.Integer, primary_key=True)
#
 #       customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'))
#
 #       date = db.Column(db.DateTime(timezone=True), default=func.now())
  #      prod_id = db.Column(db.String(200))
   #     pay_Intent = db.Column(db.String(200))
    #    shipping = db.Column(db.String(500))
     #   billing = db.Column(db.String(500))
    
