# encoding: utf-8
import os


def _database_url():
    url = os.environ.get('DATABASE_URL', 'sqlite:///dev.db')
    # Normalize to the psycopg2 driver we bundle; plain postgres:// and postgresql://
    # resolve to different drivers depending on the SQLAlchemy version
    for prefix in ('postgres://', 'postgresql://'):
        if url.startswith(prefix):
            url = 'postgresql+psycopg2://' + url[len(prefix):]
    return url


class BaseConfig(object):
    # Order matters: 'api' must register the blueprint before 'ski' attaches its namespace
    ENABLED_MODULES = (
        'api',
        'ski',
    )

    SWAGGER_UI_JSONEDITOR = True

    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Rate limiting. In Lambda the default in-memory storage is per container, so
    # the API Gateway throttle in template.yaml is the hard global limit.
    RATELIMIT_ENABLED = True
    RATELIMIT_DEFAULT = os.environ.get('RATELIMIT_DEFAULT', '60 per minute;1000 per day')
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')
    RATELIMIT_HEADERS_ENABLED = True

    CACHE_MAX_AGE_SECONDS = int(os.environ.get('CACHE_MAX_AGE_SECONDS', '300'))

    # Scheduler (local development only; Lambda uses EventBridge)
    SCHEDULER_ENABLED = False
    SCHEDULER_POLL_INTERVAL_MINUTES = 30

    # Providers
    ENABLE_REAL_PROVIDERS = False

    # Keep the free-tier database small
    CONDITIONS_RETENTION_DAYS = int(os.environ.get('CONDITIONS_RETENTION_DAYS', '7'))


class DevelopmentConfig(BaseConfig):
    """config for DevelopmentConfig."""
    DEBUG = True
    DEVELOPMENT = True
    SCHEDULER_POLL_INTERVAL_MINUTES = 5


class ProductionConfig(BaseConfig):
    """config for AWS Lambda + hosted Postgres."""
    DEBUG = False
    DEVELOPMENT = False
    SWAGGER_UI_JSONEDITOR = False

    # Lambda containers come and go; keep connections minimal and validated
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 1,
        'max_overflow': 0,
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
