from flask import current_app
from datetime import datetime, timedelta
from .models import db, Provider, Resort, Condition, FetchLog
from sqlalchemy import func
from .providers.mock import MockProvider
from .providers.openmeteo import OpenMeteoProvider
from .providers.osm import OsmProvider

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


def _get_provider(session, slug, name, type_, endpoint=None):
    provider = session.query(Provider).filter_by(slug=slug).first()
    if not provider:
        provider = Provider(name=name, slug=slug, type=type_, endpoint=endpoint, enabled=True)
        session.add(provider)
        session.commit()
    return provider


def _remove_mock_data(session):
    mock = session.query(Provider).filter_by(slug='mock').first()
    if not mock:
        return
    ids = [i for (i,) in session.query(Resort.id).filter_by(provider_id=mock.id)]
    if ids:
        Condition.query.filter(Condition.resort_id.in_(ids)).delete(synchronize_session=False)
        Resort.query.filter(Resort.id.in_(ids)).delete(synchronize_session=False)


def seed_resorts(force=False):
    """Load the bundled OpenStreetMap resort list. One-time: does nothing once resorts exist
    unless force=True, which inserts only resorts that are missing. Returns rows inserted."""
    session = db.session
    osm = _get_provider(session, 'osm', 'OpenStreetMap', 'resorts')
    if not force and session.query(Resort.id).filter_by(provider_id=osm.id).first():
        return 0

    existing = {e for (e,) in session.query(Resort.external_id).filter_by(provider_id=osm.id)}
    now = datetime.utcnow()
    fields = ('external_id', 'name', 'location', 'lat', 'lng', 'website')
    new = [
        Resort(provider_id=osm.id, source_updated_at=now, **{k: r.get(k) for k in fields})
        for r in OsmProvider().fetch_resorts()
        if r['external_id'] not in existing
    ]
    session.add_all(new)
    _remove_mock_data(session)
    session.commit()
    return len(new)


def poll_conditions(batch_size=None):
    """Fetch weather for the resorts with the oldest (or no) conditions. Returns rows stored.

    Refreshing a slice per run keeps us inside Open-Meteo's free daily limit."""
    session = db.session
    batch_size = batch_size or current_app.config['POLL_BATCH_SIZE']
    provider = _get_provider(session, 'open-meteo', 'Open-Meteo', 'weather', 'https://api.open-meteo.com/v1/forecast')

    log = FetchLog(provider_id=provider.id, started_at=datetime.utcnow(), status='running')
    session.add(log)
    session.flush()

    try:
        latest = (
            session.query(Condition.resort_id.label('rid'), func.max(Condition.fetched_at).label('last'))
            .group_by(Condition.resort_id)
            .subquery()
        )
        resorts = (
            session.query(Resort)
            .outerjoin(latest, latest.c.rid == Resort.id)
            .filter(Resort.lat.isnot(None), Resort.lng.isnot(None))
            .order_by(latest.c.last.asc().nullsfirst(), Resort.id)
            .limit(batch_size)
            .all()
        )
        by_ext = {r.external_id: r for r in resorts}
        conditions = OpenMeteoProvider().fetch_conditions_for(
            [{'external_id': r.external_id, 'lat': r.lat, 'lng': r.lng} for r in resorts]
        )
        stored = 0
        for cond in conditions:
            resort = by_ext.get(cond['external_id'])
            if resort:
                _upsert_condition(session, provider, cond, resort)
                stored += 1

        log.finished_at = datetime.utcnow()
        log.status = 'ok'
        log.record_count = stored
        provider.last_fetch_at = datetime.utcnow()
        session.commit()
        return stored
    except Exception as exc:
        session.rollback()
        log = session.merge(log)
        log.finished_at = datetime.utcnow()
        log.status = 'error'
        log.error_message = str(exc)
        session.commit()
        raise


def _poll_mock():
    session = db.session
    provider = _get_provider(session, 'mock', 'Mock Provider', 'mock')
    log = FetchLog(provider_id=provider.id, started_at=datetime.utcnow(), status='running')
    session.add(log)
    session.flush()

    try:
        prov = MockProvider(current_app)
        record_count = 0
        for r in prov.fetch_resorts():
            _upsert_resort(session, provider, r)
            record_count += 1

        for cond in prov.fetch_conditions():
            resort = session.query(Resort).filter_by(provider_id=provider.id, external_id=cond.get('external_id')).first()
            if resort:
                _upsert_condition(session, provider, cond, resort)
                record_count += 1

        log.finished_at = datetime.utcnow()
        log.status = 'ok'
        log.record_count = record_count
        provider.last_fetch_at = datetime.utcnow()
        session.commit()
        return {'conditions': record_count}
    except Exception as exc:
        session.rollback()
        log = session.merge(log)
        log.finished_at = datetime.utcnow()
        log.status = 'error'
        log.error_message = str(exc)
        session.commit()
        raise


def poll_providers(reseed=False):
    """Entry point for the poller: DATA_SOURCE=live seeds resorts once then refreshes weather;
    DATA_SOURCE=mock (local default) writes the fake sample data."""
    app = current_app._get_current_object()
    with app.app_context():
        if app.config.get('DATA_SOURCE') == 'live':
            seeded = seed_resorts(force=reseed)
            return {'seeded': seeded, 'conditions': poll_conditions()}
        return _poll_mock()

def prune_conditions():
    """Delete conditions older than CONDITIONS_RETENTION_DAYS; returns rows removed."""
    days = current_app.config.get('CONDITIONS_RETENTION_DAYS', 7)
    cutoff = datetime.utcnow() - timedelta(days=days)
    removed = Condition.query.filter(Condition.fetched_at < cutoff).delete(synchronize_session=False)
    db.session.commit()
    return removed


def init_scheduler(app):
    """Local-development scheduler; in AWS the poller Lambda is triggered by EventBridge."""
    from apscheduler.schedulers.background import BackgroundScheduler

    global _scheduler
    if _scheduler:
        return _scheduler

    scheduler = BackgroundScheduler()
    interval = app.config.get('SCHEDULER_POLL_INTERVAL_MINUTES', 5)
    scheduler.add_job(func=poll_providers, trigger='interval', minutes=interval, id='poll_providers')
    scheduler.start()
    _scheduler = scheduler
    return scheduler

