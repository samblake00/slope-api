# encoding: utf-8
"""
Ski resources: /resorts and /conditions
"""
from flask_restx import fields, Namespace
from flask import request
from flask_restx import Resource
from app.models import Resort, Condition
from app.modules.ski import SkiNamespace

# Define namespace here so we avoid circular imports and ensure RESTX symbols are
# available where resources are declared.
ski_ns = Namespace('ski', description=SkiNamespace.description)

# RESTX models
resort_model = ski_ns.model('Resort', {
    'id': fields.Integer(required=True, description='Resort ID'),
    'name': fields.String(required=True, description='Resort name'),
    'location': fields.String(description='Location'),
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
    'status': fields.String(description='Current status e.g., open/closed'),
})


@ski_ns.route('/resorts')
class ResortsResource(Resource):
    @ski_ns.marshal_list_with(resort_model)
    def get(self):
        """List resorts. Optional query param: name (substring match)"""
        q = request.args.get('name')
        query = Resort.query
        if q:
            query = query.filter(Resort.name.ilike(f"%{q}%"))
        results = []
        for r in query.all():
            results.append({
                'id': r.id,
                'name': r.name,
                'location': r.location,
                'opens': r.opens,
                'closes': r.closes,
                'runs_open': None,
                'total_runs': r.total_runs,
                'website': r.website,
            })
        return results


@ski_ns.route('/resorts/<int:resort_id>')
class ResortResource(Resource):
    @ski_ns.marshal_with(resort_model)
    def get(self, resort_id):
        """Get resort by id"""
        r = Resort.query.get(resort_id)
        if not r:
            ski_ns.abort(404, 'Resort not found')
        return {
            'id': r.id,
            'name': r.name,
            'location': r.location,
            'opens': r.opens,
            'closes': r.closes,
            'runs_open': None,
            'total_runs': r.total_runs,
            'website': r.website,
        }


@ski_ns.route('/conditions')
class ConditionsResource(Resource):
    @ski_ns.marshal_list_with(condition_model)
    def get(self):
        """List current conditions. Optional param: resort_id"""
        rid = request.args.get('resort_id')
        query = Condition.query
        if rid:
            try:
                rid = int(rid)
            except ValueError:
                ski_ns.abort(400, 'resort_id must be integer')
            query = query.filter_by(resort_id=rid)
        results = []
        for c in query.order_by(Condition.fetched_at.desc()).limit(100).all():
            results.append({
                'resort_id': c.resort_id,
                'temperature_c': c.temperature_c,
                'snow_depth_cm': c.snow_depth_cm,
                'status': c.status,
            })
        return results


@ski_ns.route('/conditions/<int:resort_id>')
class ConditionResource(Resource):
    @ski_ns.marshal_with(condition_model)
    def get(self, resort_id):
        """Get conditions for a resort"""
        c = Condition.query.filter_by(resort_id=resort_id).order_by(Condition.fetched_at.desc()).first()
        if not c:
            ski_ns.abort(404, 'Conditions not found for resort')
        return {
            'resort_id': c.resort_id,
            'temperature_c': c.temperature_c,
            'snow_depth_cm': c.snow_depth_cm,
            'status': c.status,
        }
