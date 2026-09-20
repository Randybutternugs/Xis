"""Standalone TullSite admin panel.

Runs on ARCS, separate from the website it administers. Excluded from the
GAE deploy via .gcloudignore — `gcloud app deploy` ships xissite/ only.
"""

from flask import Flask

from .config import Config


def create_app(config=None):
    app = Flask(__name__)
    app.config["PANEL"] = config or Config.from_env()

    from .api import bp as api_bp
    from .views import bp as views_bp

    app.register_blueprint(api_bp)
    app.register_blueprint(views_bp)
    return app
