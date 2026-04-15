from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.group import Group
from app.api.v1 import v1_bp
from app.api.v1.utils import success_response, error_response, require_group_role
from app.routes.reports import get_report_data

@v1_bp.route('/groups/<int:group_id>/report/', methods=['GET'])
@jwt_required()
@require_group_role(['admin'])
def get_report(group_id):
    # Reuse our existing robust report data aggregator from the web app
    data = get_report_data(group_id)
    
    # We must cleanly format this entirely into strict JSON natively
    result = {
        "group": {
            "id": data['group'].id,
            "name": data['group'].name,
            "description": data['group'].description
        },
        "generated_at": data['generated_at'].isoformat() if data['generated_at'] else None,
        "generated_by": {
            "id": data['generated_by'].id,
            "username": data['generated_by'].username
        },
        "summary": {
            "total_tasks": data['total_tasks'],
            "completed_tasks": data['completed_tasks'],
            "pending_tasks": data['pending_tasks'],
            "completion_rate": data['completion_rate']
        },
        "tasks": [{
            "id": t.id,
            "title": t.title,
            "status": 'done' if t.is_completed else 'todo',
            "is_completed": t.is_completed,
            "deadline": t.deadline.isoformat() if t.deadline else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            "assigned_to": {
                "id": t.assigned_user.id,
                "username": t.assigned_user.username
            } if t.assigned_user else None
        } for t in data['tasks']],
        "members": data['member_stats'],
        "recent_activity": [{
            "id": a.id,
            "action_type": a.action_type,
            "description": a.description,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "user": {
                "id": a.user.id,
                "username": a.user.username
            } if a.user else None
        } for a in data['activities']]
    }
    
    return success_response(result)
