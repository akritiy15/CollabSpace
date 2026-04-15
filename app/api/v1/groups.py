from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.group import Group, GroupMember
from app.models.user import User
from app.api.v1 import v1_bp
from app.api.v1.utils import success_response, error_response, require_group_member
from datetime import datetime, timezone

@v1_bp.route('/groups/', methods=['GET'])
@jwt_required()
def get_groups():
    user_id = get_jwt_identity()
    memberships = GroupMember.query.filter_by(user_id=user_id).all()
    
    result = []
    for m in memberships:
        g = m.group
        tasks = g.tasks.all()
        completed = sum(1 for t in tasks if t.is_completed)
        result.append({
            "id": g.id,
            "name": g.name,
            "description": g.description,
            "invite_code": g.invite_code,
            "member_count": g.members.count(),
            "task_count": len(tasks),
            "completed_task_count": completed,
            "user_role": m.role,
            "created_at": g.created_at.isoformat() if g.created_at else None
        })
        
    return success_response(result)

@v1_bp.route('/groups/', methods=['POST'])
@jwt_required()
def create_group():
    data = request.get_json()
    if not data or not data.get('name'):
        return error_response("Name required", 400)
    if len(data.get('name', '')) > 100:
        return error_response("Name too long", 400)
        
    user_id = get_jwt_identity()
    group = Group(
        name=data['name'],
        description=data.get('description', ''),
        created_by=user_id
    )
    group.generate_invite_code()
    db.session.add(group)
    db.session.flush()
    
    member = GroupMember(
        group_id=group.id,
        user_id=user_id,
        role='admin'
    )
    db.session.add(member)
    db.session.commit()
    
    from app.utils.activity import log_activity
    log_activity(group.id, user_id, 'MEMBER_JOINED', 'created and joined the group')
    
    return success_response({
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "invite_code": group.invite_code,
        "created_at": group.created_at.isoformat() if group.created_at else None
    }, 201)

@v1_bp.route('/groups/<int:group_id>/', methods=['GET'])
@jwt_required()
@require_group_member
def get_group_detail(group_id):
    group = Group.query.get_or_404(group_id)
    
    # Members
    members = [{
        "id": m.user.id,
        "username": m.user.username,
        "role": m.role,
        "profile_picture": m.user.profile_picture,
        "joined_at": m.joined_at.isoformat() if m.joined_at else None
    } for m in group.members.all()]
    
    # Tasks
    tasks = group.tasks.order_by(db.text('created_at DESC')).all()
    completed = sum(1 for t in tasks if t.is_completed)
    recent_tasks = [{
        "id": t.id,
        "title": t.title,
        "status": 'done' if t.is_completed else 'todo'
    } for t in tasks[:5]]
    
    total_exp = 0.0
    
    return success_response({
        "group": {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "invite_code": group.invite_code,
            "created_at": group.created_at.isoformat() if group.created_at else None
        },
        "members": members,
        "recent_tasks": recent_tasks,
        "stats": {
            "total_tasks": len(tasks),
            "completed_tasks": completed,
            "pending_tasks": len(tasks) - completed,
            "total_expenses": total_exp
        }
    })

@v1_bp.route('/groups/<int:group_id>/members/', methods=['GET'])
@jwt_required()
@require_group_member
def get_group_members(group_id):
    group = Group.query.get_or_404(group_id)
    members = [{
        "id": m.user.id,
        "username": m.user.username,
        "email": m.user.email,
        "role": m.role,
        "profile_picture": m.user.profile_picture,
        "joined_at": m.joined_at.isoformat() if m.joined_at else None
    } for m in group.members.all()]
    
    return success_response(members)
