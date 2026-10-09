from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app
from datetime import datetime, timedelta
from .models import db, Provider, Resort, Condition, FetchLog
from .providers.mock import MockProvider

_scheduler = None


def _upsert_resort(session, provider_obj, r):
    ext_id = r.get('external_id')
    resort = session.query(Resort).filter_by(provider_id=provider_obj.id, external_id=ext_id).first()
    if not resort:
        resort = Resort(
            external_id=ext_id,
            name=r.get('name'),
            location=r.get('location'),
            lat=r.get('lat'),
            lng=r.get('lng'),
            opens=r.get('opens'),
            closes=r.get('closes'),
            total_runs=r.get('total_runs'),
            website=r.get('website'),
            provider=provider_obj,
            source_updated_at=datetime.utcnow(),
        )
        session.add(resort)
        session.flush()
    else:
        resort.name = r.get('name')
        resort.location = r.get('location')
        resort.lat = r.get('lat')
        resort.lng = r.get('lng')
        resort.opens = r.get('opens')
        resort.closes = r.get('closes')
        resort.total_runs = r.get('total_runs')
        resort.source_updated_at = datetime.utcnow()
        session.add(resort)
    return resort


def _upsert_condition(session, provider_obj, cond, resort):
    c = Condition(
        resort_id=resort.id,
        provider_id=provider_obj.id,
        temperature_c=cond.get('temperature_c'),
        snow_depth_cm=cond.get('snow_depth_cm'),
        runs_open=cond.get('runs_open'),
        status=cond.get('status'),
        observed_at=cond.get('observed_at') or datetime.utcnow(),
        fetched_at=datetime.utcnow(),
    )
    session.add(c)
    return c


def poll_providers():
    app = current_app._get_current_object()
    with app.app_context():
        session = db.session
        # Ensure mock provider entry exists
        provider = session.query(Provider).filter_by(slug='mock').first()
        if not provider:
            provider = Provider(name='Mock Provider', slug='mock', type='mock', endpoint=None, enabled=True)
            session.add(provider)
            session.commit()

        log = FetchLog(provider_id=provider.id, started_at=datetime.utcnow(), status='running')
        session.add(log)
        session.flush()

        try:
            prov = MockProvider(app)
            resorts = prov.fetch_resorts()
            record_count = 0
            for r in resorts:
                resort = _upsert_resort(session, provider, r)
                record_count += 1

            # fetch conditions
            conditions = prov.fetch_conditions()
            for cond in conditions:
                resort = session.query(Resort).filter_by(provider_id=provider.id, external_id=cond.get('external_id')).first()
                if resort:
                    _upsert_condition(session, provider, cond, resort)
                    record_count += 1

            log.finished_at = datetime.utcnow()
            log.status = 'ok'
            log.record_count = record_count
            provider.last_fetch_at = datetime.utcnow()
            session.add(provider)
            session.add(log)
            session.commit()
        except Exception as exc:
            session.rollback()
            log.finished_at = datetime.utcnow()
            log.status = 'error'
            log.error_message = str(exc)
            session.add(log)
            session.commit()
            raise


def prune_conditions():
    """Delete conditions older than CONDITIONS_RETENTION_DAYS; returns rows removed."""
    days = current_app.config.get('CONDITIONS_RETENTION_DAYS', 7)
    cutoff = datetime.utcnow() - timedelta(days=days)
    removed = Condition.query.filter(Condition.fetched_at < cutoff).delete(synchronize_session=False)
    db.session.commit()
    return removed


def init_scheduler(app):
    """Initialize a BackgroundScheduler to poll providers."""
    global _scheduler
    if _scheduler:
        return _scheduler

    scheduler = BackgroundScheduler()
    interval = app.config.get('SCHEDULER_POLL_INTERVAL_MINUTES', 5)
    scheduler.add_job(func=poll_providers, trigger='interval', minutes=interval, id='poll_providers')
    scheduler.start()
    _scheduler = scheduler
    return scheduler

