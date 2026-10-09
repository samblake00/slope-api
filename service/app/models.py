from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

# SQLAlchemy db instance; will be initialized in create_app
db = SQLAlchemy()


class Provider(db.Model):
    __tablename__ = 'providers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    slug = db.Column(db.String(64), unique=True, nullable=False)
    type = db.Column(db.String(32), nullable=False)
    endpoint = db.Column(db.String(256), nullable=True)
    enabled = db.Column(db.Boolean, default=True)
    last_fetch_at = db.Column(db.DateTime, nullable=True)


class Resort(db.Model):
    __tablename__ = 'resorts'
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(128), nullable=True, index=True)
    name = db.Column(db.String(256), nullable=False)
    location = db.Column(db.String(256), nullable=True)
    lat = db.Column(db.Float, nullable=True)
    lng = db.Column(db.Float, nullable=True)
    opens = db.Column(db.String(16), nullable=True)
    closes = db.Column(db.String(16), nullable=True)
    total_runs = db.Column(db.Integer, nullable=True)
    website = db.Column(db.String(256), nullable=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('providers.id'), nullable=True)
    source_updated_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    provider = db.relationship('Provider', backref='resorts')
    conditions = db.relationship('Condition', backref='resort', lazy='dynamic')


class Condition(db.Model):
    __tablename__ = 'conditions'
    id = db.Column(db.Integer, primary_key=True)
    resort_id = db.Column(db.Integer, db.ForeignKey('resorts.id'), nullable=False, index=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('providers.id'), nullable=True)
    temperature_c = db.Column(db.Float, nullable=True)
    snow_depth_cm = db.Column(db.Float, nullable=True)
    runs_open = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(64), nullable=True)
    observed_at = db.Column(db.DateTime, nullable=True)
    fetched_at = db.Column(db.DateTime, default=datetime.utcnow)


class FetchLog(db.Model):
    __tablename__ = 'fetch_logs'
    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('providers.id'), nullable=True)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(32), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    record_count = db.Column(db.Integer, nullable=True)


