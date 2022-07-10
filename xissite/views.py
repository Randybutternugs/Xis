from flask import Blueprint, render_template, flash, request
from flask_wtf import FlaskForm, RecaptchaField
from flask_wtf.csrf import CSRFProtect
from wtforms import TextAreaField, SubmitField, RadioField, StringField, IntegerField
from wtforms.validators import DataRequired, Length, InputRequired, Email, Optional
from . import db

from .models import FeedBack

csrf = CSRFProtect()

views = Blueprint('views', __name__)

@views.route('/')
def home():
    return render_template("home.html")

@views.route('/sell')
@csrf.exempt
def sale():
    return render_template("sell.html")

@views.route('/about')
def about():
    return render_template("about.html")

@views.route('/contact', methods=['GET','POST'])
def contact():
    csrf.protect()
    form = ContactForm()
    errcolo = ''

    if form.validate_on_submit():
        try:
            feedbemail = form.data['feedbackemail']
            feedbtype = form.data['feedbacktype']
            feedborderno = form.data['orderno']
            feedbfeedbackfield = form.data['feedbackfield']
            newfeedback = FeedBack(feedbackmail = feedbemail, feedbacktype = feedbtype, feedbackorderid = feedborderno, feedbackfullfield = feedbfeedbackfield)
            db.session.add(newfeedback)
            db.session.commit()
            errcolo = '#0BE12B'
            flash(u'Feedback Sent Successfully')
        except Exception as e: 
            errcolo = 'red'
            flash(u'Error: Please Check Your Information or Try Refreshing The Page')
    elif request.method == 'POST' and form.validate_on_submit() == False:
            errcolo = 'red'
            flash(u'Error: Please Check Your Information or Try Refreshing The Page')


    return render_template("contact.html", form=form, errcolo=errcolo)

class ContactForm(FlaskForm):
    feedbackemail = StringField('Email', validators=[DataRequired(), Length(min = 1, max = 40), Email(message=None, check_deliverability=True, allow_smtputf8=True, allow_empty_local=False)])
    feedbacktype = RadioField('Type of Feedback', choices=[('1','General Feedback'),('2', 'Order Feedback')], validators=[InputRequired()])
    orderno = IntegerField('Order Number', validators=[Optional()])
    feedbackfield = TextAreaField('Leave Feedback', validators=[DataRequired(), Length(min = 10, max = 599)])
    submit = SubmitField('Submit Feedback')