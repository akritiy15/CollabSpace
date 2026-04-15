from flask import Blueprint, jsonify, request, render_template, abort
from flask_login import current_user
from datetime import datetime, timezone
from app import db
from app.models.group import Group
from app.models.task import Task
from app.models.time_tracking import TimeLog, TaskEstimate
from app.utils.time_tracking import formatted_to_minutes, calculate_member_time_stats
from app.utils.activity import log_activity
from app.utils.decorators import login_required, require_role, require_account_type

time_tracking_bp = Blueprint('time_tracking', __name__, url_prefix='/groups/<int:group_id>')

@time_tracking_bp.route('/tasks/<int:task_id>/time/log', methods=['POST'])
@login_required
@require_role('viewer')
@require_account_type('student', 'team_leader')
def log_time(group_id, task_id):
    if getattr(current_user, 'mentor_profile', None):
        return jsonify({"error": "Time logging is restricted to students only"}), 403
    from app.models.group import GroupMember
    member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if member and member.role == 'admin':
        return jsonify({"error": "Time logging is restricted to students only"}), 403
    if not member or member.role not in ['editor', 'viewer']:
        return jsonify({"error": "Time logging is restricted to students only"}), 403

    task = Task.query.filter_by(id=task_id, group_id=group_id).first_or_404()
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
        
    duration_minutes = data.get('duration_minutes')
    duration_formatted = data.get('duration_formatted')
    description = data.get('description', '')
    logged_date_str = data.get('logged_date')
    
    if duration_formatted and duration_minutes is None:
        try:
            duration_minutes = formatted_to_minutes(duration_formatted)
        except ValueError as e:
            return jsonify({'success': False, 'message': str(e)}), 400
            
    if duration_minutes is None or not isinstance(duration_minutes, int) or duration_minutes <= 0:
        return jsonify({'success': False, 'message': 'Invalid duration.'}), 400
        
    if duration_minutes > 1440:
        return jsonify({'success': False, 'message': 'Cannot log more than 24 hours at once.'}), 400
        
    logged_date = datetime.now(timezone.utc).date()
    if logged_date_str:
        try:
            parsed_date = datetime.strptime(logged_date_str, '%Y-%m-%d').date()
            if parsed_date > logged_date:
                return jsonify({'success': False, 'message': 'Cannot log future dates.'}), 400
            logged_date = parsed_date
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid date format. Use YYYY-MM-DD.'}), 400

    log = TimeLog(
        task_id=task.id,
        group_id=group_id,
        user_id=current_user.id,
        description=description,
        duration_minutes=duration_minutes,
        logged_date=logged_date
    )
    db.session.add(log)
    db.session.commit()
    
    log_activity(group_id, current_user.id, 'time_logged', f"Logged {log.to_dict()['duration_formatted']} on {task.title}", metadata={'task_id': task.id})
    
    from app import socketio
    socketio.emit('time_update', {
        'task_id': task.id,
        'user_id': current_user.id,
        'username': current_user.username,
        'minutes_added': duration_minutes,
        'task_total_minutes': task.total_time_logged,
        'task_total_formatted': task.total_time_formatted,
        'task_title': task.title
    }, room=f'group_{group_id}')
    
    return jsonify({
        'success': True,
        'log': log.to_dict(),
        'task_total_minutes': task.total_time_logged,
        'task_total_formatted': task.total_time_formatted
    })

@time_tracking_bp.route('/tasks/<int:task_id>/time/estimate', methods=['POST'])
@login_required
@require_role('editor')
def set_estimate(group_id, task_id):
    from app.models.group import GroupMember
    member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not member or member.role != 'editor':
        return jsonify({'success': False, 'message': 'Only students can set time estimates.'}), 403

    task = Task.query.filter_by(id=task_id, group_id=group_id).first_or_404()
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
        
    estimated_minutes = data.get('estimated_minutes')
    estimated_formatted = data.get('estimated_formatted')
    
    if estimated_formatted and estimated_minutes is None:
        try:
            estimated_minutes = formatted_to_minutes(estimated_formatted)
        except ValueError as e:
            return jsonify({'success': False, 'message': str(e)}), 400
            
    if estimated_minutes is None or not isinstance(estimated_minutes, int) or estimated_minutes < 0:
        return jsonify({'success': False, 'message': 'Invalid estimated time.'}), 400
        
    estimate = TaskEstimate.query.filter_by(task_id=task.id).first()
    if not estimate:
        estimate = TaskEstimate(task_id=task.id, created_by=current_user.id)
        db.session.add(estimate)
        
    estimate.estimated_minutes = estimated_minutes
    db.session.commit()
    
    from app import socketio
    socketio.emit('time_update', {
        'task_id': task.id,
        'estimated_minutes': estimate.estimated_minutes,
        'estimated_formatted': estimate.to_dict()['estimated_formatted']
    }, room=f'group_{group_id}')
    
    return jsonify({
        'success': True,
        'estimate': estimate.to_dict()
    })

@time_tracking_bp.route('/time/logs/<int:log_id>', methods=['DELETE'])
@login_required
@require_role('viewer')
def delete_time_log(group_id, log_id):
    if getattr(current_user, 'mentor_profile', None):
        return jsonify({"error": "Time logging is restricted to students only"}), 403
    from app.models.group import GroupMember
    member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if member and member.role == 'admin':
        return jsonify({"error": "Time logging is restricted to students only"}), 403
    if not member or member.role not in ['editor', 'viewer']:
        return jsonify({"error": "Time logging is restricted to students only"}), 403
        
    log = TimeLog.query.filter_by(id=log_id, group_id=group_id).first_or_404()
    
    if log.user_id != current_user.id:
        abort(403)
        
    task_id = log.task_id
    db.session.delete(log)
    db.session.commit()
    
    task = Task.query.get(task_id)
    
    from app import socketio
    socketio.emit('time_update', {
        'task_id': task_id,
        'task_total_minutes': task.total_time_logged,
        'task_total_formatted': task.total_time_formatted
    }, room=f'group_{group_id}')
    
    return jsonify({'success': True})

@time_tracking_bp.route('/time', methods=['GET'])
@login_required
@require_role('viewer')
def overview(group_id):
    group = Group.query.get_or_404(group_id)
    stats = calculate_member_time_stats(group_id)
    recent_logs = TimeLog.query.filter_by(group_id=group_id).order_by(TimeLog.logged_date.desc(), TimeLog.created_at.desc()).limit(50).all()
    return render_template('time_tracking/overview.html', group=group, stats=stats, recent_logs=recent_logs)

@time_tracking_bp.route('/time/my', methods=['GET'])
@login_required
@require_role('viewer')
def my_time(group_id):
    group = Group.query.get_or_404(group_id)
    stats = calculate_member_time_stats(group_id, user_id=current_user.id)
    recent_logs = TimeLog.query.filter_by(group_id=group_id, user_id=current_user.id).order_by(TimeLog.logged_date.desc(), TimeLog.created_at.desc()).all()
    tasks_assigned = Task.query.filter_by(group_id=group_id, assigned_to=current_user.id).all()
    return render_template('time_tracking/my_time.html', group=group, stats=stats, recent_logs=recent_logs, tasks_assigned=tasks_assigned)

@time_tracking_bp.route('/tasks/<int:task_id>/time', methods=['GET'])
@login_required
@require_role('viewer')
def task_time(group_id, task_id):
    logs = TimeLog.query.filter_by(group_id=group_id, task_id=task_id).order_by(TimeLog.created_at.desc()).all()
    return jsonify([log.to_dict() for log in logs])

@time_tracking_bp.route('/tasks/<int:task_id>/time/start', methods=['POST'])
@login_required
@require_role('viewer')
@require_account_type('student', 'team_leader')
def start_timer(group_id, task_id):
    if getattr(current_user, 'mentor_profile', None):
        return jsonify({"error": "Time logging is restricted to students only"}), 403
    from app.models.group import GroupMember
    member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if member and member.role == 'admin':
        return jsonify({"error": "Time logging is restricted to students only"}), 403
    if not member or member.role not in ['editor', 'viewer']:
        return jsonify({"error": "Time logging is restricted to students only"}), 403
        
    task = Task.query.filter_by(id=task_id, group_id=group_id).first_or_404()
    
    running_log = TimeLog.query.filter_by(user_id=current_user.id, group_id=group_id, is_running=True).first()
    if running_log:
        return jsonify({'success': False, 'message': 'Timer already running on another task'}), 400
        
    log = TimeLog(
        task_id=task.id,
        group_id=group_id,
        user_id=current_user.id,
        duration_minutes=0,
        logged_date=datetime.now(timezone.utc).date(),
        timer_start=datetime.now(timezone.utc),
        is_running=True
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({'success': True, 'log_id': log.id, 'timer_start': log.timer_start.isoformat()})

@time_tracking_bp.route('/time/logs/<int:log_id>/stop', methods=['POST'])
@login_required
@require_role('viewer')
@require_account_type('student', 'team_leader')
def stop_timer(group_id, log_id):
    if getattr(current_user, 'mentor_profile', None):
        return jsonify({"error": "Time logging is restricted to students only"}), 403
    from app.models.group import GroupMember
    member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if member and member.role == 'admin':
        return jsonify({"error": "Time logging is restricted to students only"}), 403
    if not member or member.role not in ['editor', 'viewer']:
        return jsonify({"error": "Time logging is restricted to students only"}), 403

    log = TimeLog.query.filter_by(id=log_id, group_id=group_id, user_id=current_user.id, is_running=True).first_or_404()
    
    end_time = datetime.now(timezone.utc)
    diff = end_time - (log.timer_start.replace(tzinfo=timezone.utc) if log.timer_start.tzinfo is None else log.timer_start)
    duration_minutes = int(diff.total_seconds() / 60)
    
    log.duration_minutes = duration_minutes if duration_minutes > 0 else 1
    log.is_running = False
    
    db.session.commit()
    
    task = Task.query.get(log.task_id)
    log_activity(group_id, current_user.id, 'time_logged', f"Logged {duration_minutes}m via timer on {task.title}", metadata={'task_id': task.id})
    
    from app import socketio
    socketio.emit('time_update', {
        'task_id': task.id,
        'user_id': current_user.id,
        'username': current_user.username,
        'minutes_added': duration_minutes,
        'task_total_minutes': task.total_time_logged,
        'task_total_formatted': task.total_time_formatted,
        'task_title': task.title
    }, room=f'group_{group_id}')
    
    return jsonify({
        'success': True, 
        'duration_minutes': log.duration_minutes,
        'task_total_minutes': task.total_time_logged,
        'task_total_formatted': task.total_time_formatted
    })
