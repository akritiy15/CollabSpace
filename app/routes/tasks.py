from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from datetime import datetime
from app.models.group import Group, GroupMember
from app.models.task import Task
from app.utils.activity import log_activity
from app.utils.decorators import require_role, require_account_type
from app import db
from app import socketio

tasks_bp = Blueprint('tasks', __name__, url_prefix='/groups/<int:group_id>/tasks')

@tasks_bp.url_value_preprocessor
def pull_group_id(endpoint, values):
    if values and 'group_id' in values:
        group_id = values.get('group_id')
        if current_user.is_authenticated:
            member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
            if not member:
                abort(403)

@tasks_bp.route('/')
@login_required
def index(group_id):
    if getattr(current_user, 'mentor_profile', None):
        return redirect(url_for('mentor.dashboard'))
        
    from app.models.group import GroupMember
    member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if member and member.role == 'admin':
        return redirect(url_for('tasks.team_leader_dashboard', group_id=group_id))
        
    group = Group.query.get_or_404(group_id)
    
    status = request.args.get('status')
    assigned = request.args.get('assigned')
    sort = request.args.get('sort', 'newest')
    
    query = Task.query.filter_by(group_id=group_id)
    
    if status in ['todo', 'in_progress', 'done']:
        query = query.filter_by(status=status)
        
    if assigned == 'me':
        query = query.filter_by(assigned_to=current_user.id)
        
    if sort == 'oldest':
        query = query.order_by(Task.created_at.asc())
    elif sort == 'deadline':
        query = query.order_by(Task.deadline.asc().nullslast(), Task.created_at.desc())
    else: # newest
        query = query.order_by(Task.created_at.desc())
        
    tasks = query.all()
    
    counts = {
        'all': Task.query.filter_by(group_id=group_id).count(),
        'todo': Task.query.filter_by(group_id=group_id, status='todo').count(),
        'in_progress': Task.query.filter_by(group_id=group_id, status='in_progress').count(),
        'done': Task.query.filter_by(group_id=group_id, status='done').count()
    }
    
    members = group.members.all()
    
    from app.models.time_tracking import TimeLog
    running_log = TimeLog.query.filter_by(group_id=group_id, user_id=current_user.id, is_running=True).first()
    
    return render_template('tasks/index.html', group=group, tasks=tasks, members=members, counts=counts, running_log=running_log)

from flask import redirect, url_for
@tasks_bp.route('/team-leader')
@login_required
@require_role('admin')
def team_leader_dashboard(group_id):
    group = Group.query.get_or_404(group_id)
    tasks = Task.query.filter_by(group_id=group_id).order_by(Task.created_at.desc()).all()
    members = group.members.filter(GroupMember.role.in_(['editor', 'viewer'])).all()
    return render_template('tasks/team_leader.html', group=group, tasks=tasks, members=members)


@tasks_bp.route('/create', methods=['POST'])
@login_required
@require_role('editor')
def create(group_id):
    data = request.form if request.form else request.json
    title = data.get('title')
    description = data.get('description')
    assigned_to = data.get('assigned_to')
    deadline_str = data.get('deadline')
    
    if not title:
        return jsonify({'success': False, 'message': 'Title is required'})
        
    task = Task(title=title, description=description, group_id=group_id, status='todo', created_by=current_user.id)
    
    if assigned_to and str(assigned_to) != "0":
        member = GroupMember.query.filter_by(group_id=group_id, user_id=assigned_to).first()
        if not member:
            return jsonify({'success': False, 'message': 'Assignee is not a member of this group'})
        task.assigned_to = int(assigned_to)
        
    if deadline_str:
        try:
            task.deadline = datetime.strptime(deadline_str, '%Y-%m-%d')
        except ValueError:
            pass 
            
    db.session.add(task)
    db.session.commit()
    
    log_activity(group_id, current_user.id, 'TASK_CREATED', f"created task '{task.title}'", {'task_id': task.id})
    if task.assigned_to:
        log_activity(group_id, current_user.id, 'TASK_ASSIGNED', f"assigned task '{task.title}' to {task.assignee.username}", {'task_id': task.id, 'assigned_to': task.assigned_to})
        from app.utils.notification import create_notification
        if task.assigned_to != current_user.id:
            create_notification(task.assigned_to, f"You have been assigned a new task: '{task.title}'", f"/groups/{group_id}")
            
        from app.tasks.email_tasks import send_task_assignment_email
        try:
            send_task_assignment_email.delay(user_id=task.assigned_to, task_id=task.id, assigner_id=current_user.id, group_id=group_id)
        except Exception as e:
            print(f"Failed to dispatch email task: {e}")
        
    socketio.emit('task_update', {'action': 'created', 'task': task_to_dict(task)}, room=f'group_{group_id}')
    
    return jsonify({'success': True, 'task': task_to_dict(task)})

@tasks_bp.route('/<int:task_id>', methods=['GET'])
@login_required
def get_task(group_id, task_id):
    task = Task.query.filter_by(id=task_id, group_id=group_id).first_or_404()
    return jsonify(task_to_dict(task))

@tasks_bp.route('/<int:task_id>', methods=['PATCH'])
@login_required
@require_role('editor')
def update(group_id, task_id):
    task = Task.query.filter_by(id=task_id, group_id=group_id).first_or_404()
    data = request.form if request.form else request.json
    
    old_status = task.status
    old_assigned = task.assigned_to
    old_completed = task.is_completed
    
    if 'title' in data: task.title = data['title']
    if 'description' in data: task.description = data['description']
    
    if 'status' in data:
        new_status = data['status']
        if new_status in ['todo', 'in_progress', 'done']:
            if new_status == 'done':
                incomplete_deps = [dep for dep in task.dependencies if not dep.is_completed]
                if incomplete_deps:
                    return jsonify({'success': False, 'message': f'Cannot move to Done. Blocked by task: "{incomplete_deps[0].title}"'}), 400
            task.status = new_status
            if new_status == 'done':
                task.is_completed = True
                task.completed_at = datetime.utcnow()
            else:
                task.is_completed = False
                task.completed_at = None
                
    if 'is_completed' in data:
        is_completed_val = str(data['is_completed']).lower() in ['true', '1']
        if is_completed_val and not task.is_completed:
            incomplete_deps = [dep for dep in task.dependencies if not dep.is_completed]
            if incomplete_deps:
                return jsonify({'success': False, 'message': f'Cannot mark complete. Blocked by task: "{incomplete_deps[0].title}"'}), 400
                
        task.is_completed = is_completed_val
        if is_completed_val:
            task.status = 'done'
            task.completed_at = datetime.utcnow()
        else:
            task.status = 'todo' if task.status == 'done' else task.status
            task.completed_at = None
            
    if 'assigned_to' in data:
        assigned_to = data['assigned_to']
        if not assigned_to or str(assigned_to) == '0':
            task.assigned_to = None
        else:
            member = GroupMember.query.filter_by(group_id=group_id, user_id=assigned_to).first()
            if member:
                task.assigned_to = int(assigned_to)
                
    if 'deadline' in data:
        deadline_str = data['deadline']
        if deadline_str:
            try:
                task.deadline = datetime.strptime(deadline_str, '%Y-%m-%d')
            except ValueError:
                pass
        else:
            task.deadline = None
            
    if 'dependencies' in data:
        dep_ids = data['dependencies']
        if isinstance(dep_ids, str):
            import json
            try:
                dep_ids = json.loads(dep_ids)
            except:
                dep_ids = []
                
        deps = []
        for d_id in dep_ids:
            d = Task.query.filter_by(id=int(d_id), group_id=group_id).first()
            if d: deps.append(d)
        task.dependencies = deps
        
    db.session.commit()
    
    if task.is_completed and not old_completed:
        log_activity(group_id, current_user.id, 'TASK_COMPLETED', f"completed task '{task.title}'", {'task_id': task.id})
        
    socketio.emit('task_update', {'action': 'updated', 'task': task_to_dict(task)}, room=f'group_{group_id}')
    return jsonify({'success': True, 'task': task_to_dict(task)})

@tasks_bp.route('/<int:task_id>', methods=['DELETE'])
@login_required
@require_role('admin')
def delete(group_id, task_id):
    task = Task.query.filter_by(id=task_id, group_id=group_id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    
    log_activity(group_id, current_user.id, 'TASK_DELETED', f"deleted task '{task.title}'", {'task_id': task_id})
    socketio.emit('task_update', {'action': 'deleted', 'task_id': task_id}, room=f'group_{group_id}')
    return jsonify({'success': True})

def task_to_dict(task):
    from datetime import datetime
    overdue = False
    if task.deadline and not task.is_completed:
        if task.deadline.date() < datetime.utcnow().date():
            overdue = True
            
    return {
        'id': task.id,
        'title': task.title,
        'description': task.description,
        'status': task.status,
        'is_completed': task.is_completed,
        'assigned_to': task.assigned_to,
        'assignee_name': getattr(task.assignee, 'username', None) if getattr(task, 'assignee', None) else getattr(getattr(task, 'assigned_user', None), 'username', None),
        'assignee_avatar': getattr(task.assignee, 'profile_picture', None) if getattr(task, 'assignee', None) else getattr(getattr(task, 'assigned_user', None), 'profile_picture', None),
        'deadline_str': task.deadline.strftime('%b %d, %Y') if task.deadline else None,
        'deadline_iso': task.deadline.strftime('%Y-%m-%d') if task.deadline else None,
        'is_overdue': overdue,
        'dependencies': [{'id': d.id, 'title': d.title, 'is_completed': d.is_completed} for d in getattr(task, 'dependencies', [])],
        'group_id': task.group_id,
        'total_time_logged': getattr(task, 'total_time_logged', 0),
        'total_time_formatted': getattr(task, 'total_time_formatted', '0m'),
        'estimated_minutes': getattr(task, 'estimated_minutes', None),
        'time_variance_minutes': getattr(task, 'time_variance_minutes', None),
        'approval_status': task.approval_status,
        'approved_by': getattr(getattr(task, 'approver', None), 'username', None),
        'approved_at': task.approved_at.strftime('%Y-%m-%d %H:%M') if task.approved_at else None,
        'approval_note': task.approval_note
    }

@tasks_bp.route('/<int:task_id>/submit', methods=['POST'])
@login_required
@require_role('viewer')
@require_account_type('student', 'team_leader')
def submit_for_approval(group_id, task_id):
    task = Task.query.filter_by(id=task_id, group_id=group_id).first_or_404()
    
    member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if task.assigned_to != current_user.id and (not member or member.role not in ['admin', 'editor']):
        return jsonify({'success': False, 'message': 'Not authorized'}), 403
        
    task.approval_status = 'pending'
    db.session.commit()
    
    log_activity(group_id, current_user.id, 'TASK_SUBMITTED', f"submitted '{task.title}' for approval", {'task_id': task.id})
    socketio.emit('task_update', {'action': 'updated', 'task': task_to_dict(task)}, room=f'group_{group_id}')
    
    return jsonify({'success': True, 'task': task_to_dict(task)})

@tasks_bp.route('/<int:task_id>/approve', methods=['POST'])
@login_required
@require_role('editor')
@require_account_type('mentor', 'team_leader')
def approve_task(group_id, task_id):
    from datetime import datetime
    task = Task.query.filter_by(id=task_id, group_id=group_id).first_or_404()
    
    data = request.json or request.form
    action = data.get('action') # 'approve' or 'request_changes'
    note = data.get('note', '')
    
    if action == 'approve':
        task.approval_status = 'approved'
        task.is_completed = True
        task.status = 'done'
        task.completed_at = datetime.utcnow()
        task.approved_by = current_user.id
        task.approved_at = datetime.utcnow()
        task.approval_note = note
        
        log_activity(group_id, current_user.id, 'TASK_APPROVED', f"approved '{task.title}'", {'task_id': task.id})
        if task.assigned_to and task.assigned_to != current_user.id:
            from app.utils.notification import create_notification
            create_notification(task.assigned_to, f"Your task '{task.title}' was approved.", f"/groups/{group_id}")
        
    elif action == 'request_changes':
        task.approval_status = 'changes_requested'
        task.is_completed = False
        task.status = 'in_progress'
        task.approval_note = note
        
        log_activity(group_id, current_user.id, 'TASK_CHANGES_REQUESTED', f"requested changes on '{task.title}'", {'task_id': task.id})
        if task.assigned_to and task.assigned_to != current_user.id:
            from app.utils.notification import create_notification
            create_notification(task.assigned_to, f"Changes were requested on your task '{task.title}'.", f"/groups/{group_id}")
        
    db.session.commit()
    socketio.emit('task_update', {'action': 'updated', 'task': task_to_dict(task)}, room=f'group_{group_id}')
    
    return jsonify({'success': True, 'task': task_to_dict(task)})

@tasks_bp.route('/pending-approval', methods=['GET'])
@login_required
@require_role('editor')
@require_account_type('mentor', 'team_leader')
def pending_approval(group_id):
    tasks = Task.query.filter_by(group_id=group_id, approval_status='pending').all()
    return jsonify([task_to_dict(t) for t in tasks])
