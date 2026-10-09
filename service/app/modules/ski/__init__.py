# encoding: utf-8
"""
Ski module: exposes /resorts and /conditions endpoints using flask-restx
"""

from app import api_v1

class SkiNamespace:
    namespace = "ski"
    description = "ski resorts and conditions"


def init_app(app, **kwargs):
    # Import resources to ensure the `ski_ns` namespace and its routes are defined.
    from . import resources

    # `resources` exposes `ski_ns` — attach it to the global API under /ski
    api_v1.add_namespace(resources.ski_ns, path='/ski')

    return
