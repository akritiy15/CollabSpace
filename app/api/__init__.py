from flask import Blueprint

api_bp = Blueprint('api', __name__, url_prefix='/api')

from app.api.v1 import v1_bp
api_bp.register_blueprint(v1_bp)
