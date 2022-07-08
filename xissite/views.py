from flask import Blueprint, render_template

views = Blueprint('views', __name__)

@views.route('/')
def home():
    return render_template("home.html")

@views.route('/sell')
def sale():
    return render_template("sell.html")

@views.route('/about')
def about():
    return render_template("about.html")