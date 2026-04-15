from app.routes.auth import auth_bp
from app.routes.dashboard import dashboard_bp
from app.routes.profile import profile_bp
from app.routes.members import members_bp
from app.routes.groups import groups_bp
from app.routes.tasks import tasks_bp
from app.routes.activity import activity_bp
from app.routes.reports import reports_bp
from app.routes.time_tracking import time_tracking_bp
from app.routes.mentor import mentor_bp
from app.routes.meetings import meetings_bp

def register_routes(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(members_bp)
    app.register_blueprint(groups_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(activity_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(time_tracking_bp)
    app.register_blueprint(mentor_bp)
    app.register_blueprint(meetings_bp)
