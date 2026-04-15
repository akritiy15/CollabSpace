from functools import wraps
from flask import abort
from flask_login import current_user, login_required
from app.models.group import GroupMember

# Re-export login_required per instructions
__all__ = ['login_required', 'require_role', 'require_account_type']

def require_role(role):
    """
    Decorator to check if user has the required role in the current group.
    Returns 403 if user does not have the required role.
    Assumes group_id is a URL parameter in the route.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            group_id = kwargs.get('group_id')
            if not group_id:
                abort(403)
                
            member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
            if not member:
                abort(403)
                
            role_hierarchy = {
                'viewer': 1,
                'editor': 2,
                'admin': 3
            }
            
            user_level = role_hierarchy.get(member.role, 0)
            required_level = role_hierarchy.get(role, 0)
            
            if user_level < required_level:
                abort(403)
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_account_type(*account_types):
    """
    Decorator to check if user has the required account type.
    Returns 403 if user does not have the required account type.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
                
            if current_user.account_type not in account_types:
                abort(403)
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator
