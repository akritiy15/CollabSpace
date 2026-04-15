from flask import Blueprint, jsonify
from app.api.v1.utils import error_response

v1_bp = Blueprint('api_v1', __name__, url_prefix='/v1')

@v1_bp.errorhandler(400)
def handle_400(e):
    return error_response("Bad request", 400)

@v1_bp.errorhandler(401)
def handle_401(e):
    return error_response("Unauthorized", 401)

@v1_bp.errorhandler(403)
def handle_403(e):
    return error_response("Forbidden — insufficient permissions", 403)

@v1_bp.errorhandler(404)
def handle_404(e):
    return error_response("Resource not found", 404)

@v1_bp.errorhandler(405)
def handle_405(e):
    return error_response("Method not allowed", 405)

@v1_bp.errorhandler(500)
def handle_500(e):
    return error_response("Internal server error", 500)

from app.api.v1 import auth, groups, tasks, reports, activity
