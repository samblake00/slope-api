# encoding: utf-8
"""
Ski resources: /resorts and /conditions
"""
from flask_restx import fields, Namespace
from flask import request
from flask_restx import Resource
from sqlalchemy import and_, func
from app.models import db, Resort, Condition
from app.modules.ski import SkiNamespace

# Define namespace here so we avoid circular imports and ensure RESTX symbols are
# available where resources are declared.
ski_ns = Namespace('ski', description=SkiNamespace.description)

DEFAULT_LIMIT = 100
MAX_LIMIT = 500

# RESTX models
resort_model = ski_ns.model('Resort', {
    'id': fields.Integer(required=True, description='Resort ID'),
    'name': fields.String(required=True, description='Resort name'),
    'location': fields.String(description='Location'),
    'lat': fields.Float(description='Latitude'),
    'lng': fields.Float(description='Longitude'),
    'opens': fields.String(description='Opening time'),
    'closes': fields.String(description='Closing time'),
    'runs_open': fields.Integer(description='Number of runs open'),
    'total_runs': fields.Integer(description='Total runs'),
    'website': fields.String(description='Resort website URL'),
})

condition_model = ski_ns.model('Condition', {
    'resort_id': fields.Integer(required=True, description='Resort ID'),
    'temperature_c': fields.Float(description='Temperature in C'),
    'snow_depth_cm': fields.Float(description='Snow depth in cm'),
    'status': fields.String(description='Current status e.g., open/closed (not available for most resorts)'),
    'observed_at': fields.DateTime(dt_format='iso8601', description='When the weather was observed (UTC)'),
})

page_parser = ski_ns.parser()
page_parser.add_argument('limit', type=int, default=DEFAULT_LIMIT, help=f'Page size, 1-{MAX_LIMIT}', location='args')
page_parser.add_argument('offset', type=int, default=0, help='Number of items to skip', location='args')


def _page_args():
    try:
        limit = int(request.args.get('limit', DEFAULT_LIMIT))
        offset = int(request.args.get('offset', 0))
    except ValueError:
        ski_ns.abort(400, 'limit and offset must be integers')
    return min(max(limit, 1), MAX_LIMIT), max(offset, 0)


def _resort_dict(r):
    return {
        'id': r.id,
        'name': r.name,
        'location': r.location,
        'lat': r.lat,
        'lng': r.lng,
        'opens': r.opens,
        'closes': r.closes,
        'runs_open': None,
        'total_runs': r.total_runs,
        'website': r.website,
    }


def _condition_dict(c):
    return {
        'resort_id': c.resort_id,
        'temperature_c': c.temperature_c,
        'snow_depth_cm': c.snow_depth_cm,
        'status': c.status,
        'observed_at': c.observed_at,
    }


@ski_ns.route('/resorts')
class ResortsResource(Resource):
    @ski_ns.expect(page_parser)
    @ski_ns.marshal_list_with(resort_model)
    @ski_ns.response(200, 'Success', headers={'X-Total-Count': 'Total matching resorts'})
    def get(self):
        """List resorts (paginated). Optional query param: name (substring match)"""
        limit, offset = _page_args()
        query = Resort.query
        q = request.args.get('name')
        if q:
            query = query.filter(Resort.name.ilike(f"%{q}%"))
        total = query.count()
        rows = query.order_by(Resort.name, Resort.id).limit(limit).offset(offset).all()
        return [_resort_dict(r) for r in rows], 200, {'X-Total-Count': str(total)}


@ski_ns.route('/resorts/<int:resort_id>')
class ResortResource(Resource):
    @ski_ns.marshal_with(resort_model)
    def get(self, resort_id):
        """Get resort by id"""
        r = db.session.get(Resort, resort_id)
        if not r:
            ski_ns.abort(404, 'Resort not found')
        return _resort_dict(r)


@ski_ns.route('/conditions')
class ConditionsResource(Resource):
    @ski_ns.expect(page_parser)
    @ski_ns.marshal_list_with(condition_model)
    @ski_ns.response(200, 'Success', headers={'X-Total-Count': 'Total matching resorts with conditions'})
    def get(self):
        """Latest conditions per resort (paginated). Optional param: resort_id"""
        limit, offset = _page_args()
        latest = db.session.query(
            Condition.resort_id.label('rid'), func.max(Condition.fetched_at).label('ts')
        ).group_by(Condition.resort_id)

        rid = request.args.get('resort_id')
        if rid:
            try:
                rid = int(rid)
            except ValueError:
                ski_ns.abort(400, 'resort_id must be integer')
            latest = latest.filter(Condition.resort_id == rid)
        latest = latest.subquery()

        query = Condition.query.join(
            latest, and_(Condition.resort_id == latest.c.rid, Condition.fetched_at == latest.c.ts)
        )
        total = query.count()
        rows = query.order_by(Condition.resort_id).limit(limit).offset(offset).all()
        return [_condition_dict(c) for c in rows], 200, {'X-Total-Count': str(total)}


@ski_ns.route('/conditions/<int:resort_id>')
class ConditionResource(Resource):
    @ski_ns.marshal_with(condition_model)
    def get(self, resort_id):
        """Get conditions for a resort"""
        c = Condition.query.filter_by(resort_id=resort_id).order_by(Condition.fetched_at.desc()).first()
        if not c:
            ski_ns.abort(404, 'Conditions not found for resort')
        return _condition_dict(c)
