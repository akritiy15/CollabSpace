from flask import request
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity, get_jwt
from app.models.user import User
from app.api.v1 import v1_bp
from app.api.v1.utils import success_response, error_response

# Simple in-memory blocklist for demo purposes
token_blocklist = set()

from app import jwt
@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    jti = jwt_payload["jti"]
    return jti in token_blocklist

@v1_bp.route('/auth/login', methods=['POST'])
def auth_login():
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return error_response("Email and password required", 400)
        
    user = User.query.filter_by(email=data['email']).first()
    if not user or not user.check_password(data['password']):
        return error_response("Invalid credentials", 401)
        
    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    
    return success_response({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "profile_picture": user.profile_picture,
            "bio": user.bio
        }
    })

@v1_bp.route('/auth/refresh', methods=['POST'])
@jwt_required(refresh=True)
def auth_refresh():
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    return success_response({"access_token": access_token})

@v1_bp.route('/auth/logout', methods=['POST'])
@jwt_required()
def auth_logout():
    jti = get_jwt()["jti"]
    token_blocklist.add(jti)
    return success_response({"message": "Logged out successfully"})

@v1_bp.route('/auth/me', methods=['GET'])
@jwt_required()
def auth_me():
    user_id = get_jwt_identity()
    from app import db
    user = db.session.get(User, user_id)
    if not user:
        return error_response("User not found", 404)
        
    return success_response({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "bio": user.bio,
        "profile_picture": user.profile_picture,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "group_count": user.group_memberships.count(),
        "friend_count": user.friends.count() + user.friends_of.count()
    })
