from flask import request
from flask_jwt_extended import jwt_required
from app import db
from app.models.activity import ActivityLog
from app.api.v1 import v1_bp
from app.api.v1.utils import success_response, require_group_member

@v1_bp.route('/groups/<int:group_id>/activity/', methods=['GET'])
@jwt_required()
@require_group_member
def get_activity(group_id):
    query = ActivityLog.query.filter_by(group_id=group_id)
    
    act_filter = request.args.get('filter')
    if act_filter == 'task':
        query = query.filter(ActivityLog.action_type.in_(['TASK_CREATED', 'TASK_COMPLETED', 'TASK_ASSIGNED', 'TASK_DELETED']))
    elif act_filter == 'members':
        query = query.filter(ActivityLog.action_type.in_(['MEMBER_JOINED', 'MEMBER_LEFT', 'ROLE_CHANGED']))
    query = query.order_by(ActivityLog.created_at.desc())
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return success_response({
        "activities": [{
            "id": a.id,
            "action_type": a.action_type,
            "description": a.description,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "user": {
                "id": a.user.id,
                "username": a.user.username,
                "profile_picture": a.user.profile_picture
            } if a.user else None
        } for a in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
        "has_next": pagination.has_next
    })
