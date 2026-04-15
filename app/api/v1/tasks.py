from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.task import Task
from app.models.user import User
from app.api.v1 import v1_bp
from app.api.v1.utils import success_response, error_response, require_group_member, require_group_role
from app.utils.activity import log_activity
from datetime import datetime, timezone
import dateutil.parser

@v1_bp.route('/groups/<int:group_id>/tasks/', methods=['GET'])
@jwt_required()
@require_group_member
def get_tasks(group_id):
    query = Task.query.filter_by(group_id=group_id)
    
    status = request.args.get('status')
    if status == 'done': query = query.filter_by(is_completed=True)
    elif status in ['todo', 'in_progress']: query = query.filter_by(is_completed=False)
    
    assigned_to = request.args.get('assigned_to')
    if assigned_to == 'me':
        user_id = get_jwt_identity()
        query = query.filter_by(assigned_to=user_id)
        
    sort = request.args.get('sort', 'newest')
    if sort == 'oldest': query = query.order_by(Task.created_at.asc())
    elif sort == 'deadline': query = query.order_by(Task.deadline.asc().nullslast())
    else: query = query.order_by(Task.created_at.desc())
        
    tasks = query.all()
    result = []
    for t in tasks:
        result.append({
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "status": 'done' if t.is_completed else 'in_progress',
            "is_completed": t.is_completed,
            "deadline": t.deadline.isoformat() if t.deadline else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            "assigned_to": {
                "id": t.assigned_user.id,
                "username": t.assigned_user.username,
                "profile_picture": t.assigned_user.profile_picture
            } if t.assigned_user else None,
            "created_by": {
                "id": t.creator.id,
                "username": t.creator.username
            } if t.creator else None
        })
        
    return success_response(result)

@v1_bp.route('/groups/<int:group_id>/tasks/', methods=['POST'])
@jwt_required()
@require_group_role(['admin', 'editor'])
def create_task(group_id):
    data = request.get_json()
    if not data or not data.get('title'):
        return error_response("Title required", 400)
        
    user_id = get_jwt_identity()
    
    deadline = None
    if data.get('deadline'):
        try:
            deadline = dateutil.parser.isoparse(data['deadline'])
        except Exception:
            pass

    task = Task(
        group_id=group_id,
        title=data['title'],
        description=data.get('description', ''),
        assigned_to=data.get('assigned_to'),
        deadline=deadline,
        created_by=user_id
    )
    db.session.add(task)
    db.session.commit()
    from app.utils.activity import log_activity
    log_activity(group_id, user_id, 'TASK_CREATED', f"created task: {task.title}")
    if task.assigned_to:
        from app.tasks.email_tasks import send_task_assignment_email
        send_task_assignment_email.delay(user_id=task.assigned_to, task_id=task.id, assigner_id=user_id, group_id=group_id)
    
    from app import socketio
    from app.routes.tasks import task_to_dict
    socketio.emit('task_update', {'action': 'created', 'task': task_to_dict(task)}, room=f'group_{group_id}')
    
    return success_response({
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "is_completed": task.is_completed,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "deadline": task.deadline.isoformat() if task.deadline else None,
        "assigned_to": task.assigned_to
    }, 201)

@v1_bp.route('/groups/<int:group_id>/tasks/<int:task_id>/', methods=['PATCH'])
@jwt_required()
@require_group_role(['admin', 'editor'])
def update_task(group_id, task_id):
    task = Task.query.filter_by(id=task_id, group_id=group_id).first_or_404()
    data = request.get_json()
    if not data: return error_response("No data provided", 400)
    
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    
    if 'title' in data: task.title = data['title']
    if 'description' in data: task.description = data['description']
    if 'assigned_to' in data: 
        assigned = data['assigned_to']
        task.assigned_to = assigned
        if task.assigned_to:
            log_activity(group_id, user_id, 'TASK_ASSIGNED', f"assigned task '{task.title}'")
            from app.tasks.email_tasks import send_task_assignment_email
            send_task_assignment_email.delay(user_id=task.assigned_to, task_id=task.id, assigner_id=user_id, group_id=group_id)
            
    if 'deadline' in data:
        try: task.deadline = dateutil.parser.isoparse(data['deadline'])
        except: pass
            
    if 'status' in data:
        is_done = (data['status'] == 'done')
        if is_done and not task.is_completed:
            task.is_completed = True
            task.completed_at = datetime.now(timezone.utc)
            log_activity(group_id, user_id, 'TASK_COMPLETED', f"completed task: {task.title}")
        elif not is_done and task.is_completed:
            task.is_completed = False
            task.completed_at = None

    db.session.commit()
    
    from app import socketio
    from app.routes.tasks import task_to_dict
    socketio.emit('task_update', {'action': 'updated', 'task': task_to_dict(task)}, room=f'group_{group_id}')
    
    return success_response({
        "id": task.id,
        "title": task.title,
        "is_completed": task.is_completed,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None
    })

@v1_bp.route('/groups/<int:group_id>/tasks/<int:task_id>/', methods=['DELETE'])
@jwt_required()
@require_group_role(['admin'])
def delete_task(group_id, task_id):
    task = Task.query.filter_by(id=task_id, group_id=group_id).first_or_404()
    title = task.title
    db.session.delete(task)
    db.session.commit()
    from app.utils.activity import log_activity
    log_activity(group_id, get_jwt_identity(), 'TASK_DELETED', f"deleted task: {title}")
    
    from app import socketio
    socketio.emit('task_update', {'action': 'deleted', 'task_id': task_id}, room=f'group_{group_id}')
    
    return success_response({"message": "Task deleted"})
