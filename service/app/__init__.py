# encoding: utf-8
"""
SlopeAPI service: Flask app factory.
"""
from flask import Flask, request
from flask_restx import Api
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from .models import db
import logging
import os

limiter = Limiter(key_func=get_remote_address)

api_v1 = Api(
    version='1.0',
    title="SlopeAPI",
    description=(
        "Open ski resort and conditions data. Resorts (c) OpenStreetMap contributors (ODbL); weather by Open-Meteo.com (CC BY 4.0)."
    ),
)

def create_app(config_name=None, **kwargs):
    """
    Create and configure the Flask application.
    """

    # Initialize the Flask app
    app: Flask = Flask(__name__, **kwargs)

    # Load the config file
    app.config.from_object(config_name or os.environ.get('APP_CONFIG', 'config.DevelopmentConfig'))

    # Initialize extensions
    db.init_app(app)
    limiter.init_app(app)

    # Initialize Flask-RESTX
    api_v1.init_app(app)

    # Start scheduler (if enabled) — import here to avoid circular imports
    if app.config.get('SCHEDULER_ENABLED'):
        try:
            from . import tasks
            tasks.init_scheduler(app)
        except Exception:
            logging.exception('Failed to initialize scheduler')

    # Initialize the modules
    from . import modules
    modules.init_app(app)

    @app.after_request
    def add_cache_headers(response):
        # Lets a CDN/browser absorb repeat reads; data only changes when the poller runs
        if request.method == 'GET' and response.status_code == 200 and not response.direct_passthrough:
            response.headers.setdefault('Cache-Control', f"public, max-age={app.config['CACHE_MAX_AGE_SECONDS']}")
            response.add_etag()
            response.make_conditional(request)
        return response

    return app