# encoding: utf-8
"""
Example RESTful API Server.
"""
from flask import Flask
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
        "Open ski resort and conditions data."
    ),
)

def create_app(flask_config_name=None, **kwargs):
    """
    Entry point to the Flask RESTful Server application.
    """

    # Initialize the Flask-App
    app: Flask = Flask(__name__, **kwargs)

    # Load the config file
    app.config.from_object(flask_config_name or os.environ.get('APP_CONFIG', 'config.DevelopmentConfig'))

    # Initialize extensions
    db.init_app(app)
    limiter.init_app(app)

    # Initialize FLASK-RESTPlus
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

    return app