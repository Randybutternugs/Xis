from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from os import path

db = SQLAlchemy()
DB_NAME = "customerinfo.db"

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'kfoaew90ifq209fjoiskdf'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
    db.init_app(app)

    from .views import views
    from .auth import auth
    from .sales import sales

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/') 
    app.register_blueprint(sales, url_prefix='/') 

    from .models import Customer #, purchase_info

    create_database(app)

    return app

def create_database(app):
    if not path.exists('xissite/' + DB_NAME):
        db.create_all(app=app)
        print('Database Successfully Created.')