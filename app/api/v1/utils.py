from flask import jsonify
from functools import wraps
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from app.models.group import GroupMember

def success_response(data, status_code=200):
    return jsonify({
        "success": True,
        "data": data,
        "error": None
    }), status_code

def error_response(message, status_code):
    return jsonify({
        "success": False,
        "data": None,
        "error": message
    }), status_code

def require_group_member(f):
    @wraps(f)
    def decorated_function(group_id, *args, **kwargs):
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        member = GroupMember.query.filter_by(group_id=group_id, user_id=user_id).first()
        if not member:
            return error_response("Forbidden — insufficient permissions", 403)
        return f(group_id, *args, **kwargs)
    return decorated_function

def require_group_role(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(group_id, *args, **kwargs):
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            member = GroupMember.query.filter_by(group_id=group_id, user_id=user_id).first()
            if not member or member.role not in roles:
                return error_response("Forbidden — insufficient permissions", 403)
            return f(group_id, *args, **kwargs)
        return decorated_function
    return decorator
