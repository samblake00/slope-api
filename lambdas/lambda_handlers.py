# encoding: utf-8
"""AWS Lambda entry points."""
import os

from apig_wsgi import make_lambda_handler

from app import create_app
from app.models import db

_app = None


def _get_app():
    global _app
    if _app is None:
        _app = create_app(os.environ.get('APP_CONFIG', 'config.ProductionConfig'))
    return _app


_api_handler = None


def api_handler(event, context):
    """API Gateway HTTP API (payload v2) -> Flask."""
    global _api_handler
    if _api_handler is None:
        _api_handler = make_lambda_handler(_get_app())
    return _api_handler(event, context)


def poller_handler(event, context):
    """EventBridge schedule -> poll providers and prune old data."""
    from app.tasks import poll_providers, prune_conditions

    app = _get_app()
    with app.app_context():
        db.create_all()
        result = poll_providers(reseed=bool((event or {}).get('reseed')))
        removed = prune_conditions()
    return {'status': 'ok', 'pruned': removed, **result}
