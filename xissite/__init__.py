from flask import Flask

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'kfoaew90ifq209fjoiskdf'

    from .views import views
    from .auth import auth
    from .sales import sales

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/') 
    app.register_blueprint(sales, url_prefix='/') 

    return app
