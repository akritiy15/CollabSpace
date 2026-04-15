import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from flask_dance.contrib.google import make_google_blueprint

from config import config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
jwt = JWTManager()
socketio = SocketIO(async_mode="threading")
mail = Mail()
csrf = CSRFProtect()

def create_app(config_name='default'):
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    print("CLIENT ID:", app.config.get("GOOGLE_OAUTH_CLIENT_ID"))

    db.init_app(app)
    migrate.init_app(app, db)
    
    # 4. FLASK-LOGIN SETUP
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)
    
    jwt.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")
    mail.init_app(app)
    csrf.init_app(app)

    @app.context_processor
    def inject_group_role():
        from app.models.group import GroupMember
        from flask_login import current_user
        from flask import request
        
        group_id = request.view_args.get('group_id') if request.view_args else None
        current_group_role = None
        
        if group_id and current_user.is_authenticated:
            member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
            if member:
                current_group_role = member.role
                
        def get_group_role(gid):
            if current_user.is_authenticated:
                m = GroupMember.query.filter_by(group_id=gid, user_id=current_user.id).first()
                if m:
                    return m.role
            return None
            
        from app.utils.activity import ACTIVITY_CONFIG
        from datetime import datetime
        
        def now_local():
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
        return dict(current_group_role=current_group_role, get_group_role=get_group_role, ACTIVITY_CONFIG=ACTIVITY_CONFIG, now_local=now_local)

    # 5. GOOGLE OAUTH SETUP
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' # Necessary for local development HTTP
    google_bp = make_google_blueprint(
        client_id=app.config["GOOGLE_OAUTH_CLIENT_ID"],
        client_secret=app.config["GOOGLE_OAUTH_CLIENT_SECRET"],
        scope=[
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email",
            "openid"
        ],
        redirect_to="auth.google_auth",
        reprompt_select_account=True
    )
    app.register_blueprint(google_bp, url_prefix="/login")

    # Import models so migrations detect them
    from app import models
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))
        
    from flask import jsonify

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({"success": False, "error": "Missing token"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({"success": False, "error": "Invalid token"}), 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"success": False, "error": "Token expired"}), 401

    @jwt.user_identity_loader
    def user_identity_lookup(user):
        if hasattr(user, 'id'):
            return user.id
        return user

    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        identity = jwt_data["sub"]
        return db.session.get(User, identity)

    # Register API blueprints
    from app.api import api_bp
    app.register_blueprint(api_bp)
    csrf.exempt(api_bp) # CSRF shouldn't apply to JWT routes!

    @app.route('/api/docs')
    def api_docs():
        from flask import render_template
        return render_template('api/docs.html')

    # Register web route blueprints
    from app.routes import register_routes
    register_routes(app)

    return app
