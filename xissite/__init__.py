from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from os import path, environ
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
import uuid
import os
from dotenv import load_dotenv

# Try to load environment variables from vars.env
if os.path.exists('vars.env'):
    load_dotenv('vars.env')

db = SQLAlchemy()
DB_NAME = "customerinfo.db"

def create_app():
    app = Flask(__name__)
    
    # Use environment variable for secret key if available, otherwise generate one
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', str(uuid.uuid4()))
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
    app.config['WTF_CSRF_CHECK_DEFAULT'] = False



    csrf = CSRFProtect()
    csrf.init_app(app)
    db.init_app(app)

    from .views import views
    from .auth import auth
    from .sales import sales

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/') 
    app.register_blueprint(sales, url_prefix='/') 

    from .models import Customer, Purchase_info, User

    create_database(app)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))

    return app

def create_database(app):
    if not path.exists('xissite/' + DB_NAME):
        with app.app_context():
            db.create_all()
        print('Database Successfully Created.')