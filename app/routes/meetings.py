from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models.group import Group, GroupMember
from app.models.meeting import MeetingNote
from app.models.task import Task
from app.utils.ai_meeting import extract_tasks_from_notes
from app.utils.activity import log_activity, MEETING_ANALYZED
from datetime import date, timedelta
import json

meetings_bp = Blueprint('meetings', __name__, url_prefix='/groups/<int:group_id>/meetings')

def get_group_and_role(group_id):
    group = Group.query.get_or_404(group_id)
    membership = GroupMember.query.filter_by(group_id=group.id, user_id=current_user.id).first()
    if not membership:
        return None, None
    return group, membership.role

@meetings_bp.route('/')
@login_required
def index(group_id):
    group, role = get_group_and_role(group_id)
    if not group:
        flash("You are not a member of this group.", "danger")
        return redirect(url_for('dashboard.index'))
        
    meeting_notes = MeetingNote.query.filter_by(group_id=group.id).order_by(MeetingNote.created_at.desc()).all()
    return render_template('meetings/index.html', group=group, current_group_role=role, meeting_notes=meeting_notes)

@meetings_bp.route('/new')
@login_required
def new(group_id):
    group, role = get_group_and_role(group_id)
    if not group:
        flash("You are not a member of this group.", "danger")
        return redirect(url_for('dashboard.index'))
        
    if role not in ['admin', 'editor']:
        flash("You do not have permission to create meeting notes.", "danger")
        return redirect(url_for('meetings.index', group_id=group.id))
        
    api_configured = bool(current_app.config.get('ANTHROPIC_API_KEY'))
    members = GroupMember.query.filter_by(group_id=group.id).all()
    members_json = [{'user_id': m.user.id, 'user': {'username': m.user.username}} for m in members]
    
    return render_template('meetings/new.html', group=group, current_group_role=role, members_json=members_json, api_configured=api_configured)

@meetings_bp.route('/analyze', methods=['POST'])
@login_required
def analyze(group_id):
    group, role = get_group_and_role(group_id)
    if not group or role not in ['admin', 'editor']:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
    data = request.json
    title = data.get('title', '').strip()
    notes_text = data.get('notes_text', '').strip()
    
    if len(title) == 0 or len(title) > 200:
        return jsonify({'success': False, 'error': 'Title is required and must be under 200 characters.'})
        
    if len(notes_text) < 30:
        return jsonify({'success': False, 'error': 'Notes are too short. Please add more detail for better results.'})
        
    if not current_app.config.get('ANTHROPIC_API_KEY'):
        return jsonify({'success': False, 'error': 'AI features are not configured. Please add your Anthropic API key to the .env file.'})
        
    members = GroupMember.query.filter_by(group_id=group.id).all()
    member_list = [{'user_id': m.user.id, 'username': m.user.username} for m in members]
    
    result = extract_tasks_from_notes(notes_text, member_list, group.name)
    
    if result.get('error'):
        return jsonify({'success': False, 'error': result['error']})
        
    return jsonify({
        'success': True,
        'data': result
    })

@meetings_bp.route('/create-tasks', methods=['POST'])
@login_required
def create_tasks(group_id):
    group, role = get_group_and_role(group_id)
    if not group or role not in ['admin', 'editor']:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
    data = request.json
    title = data.get('title')
    notes_text = data.get('notes_text')
    summary = data.get('summary', '')
    key_decisions = data.get('key_decisions', [])
    selected_tasks = data.get('selected_tasks', [])
    
    if not selected_tasks:
        return jsonify({'success': False, 'error': 'No tasks selected.'})
        
    # Create MeetingNote
    meeting = MeetingNote(
        group_id=group.id,
        created_by=current_user.id,
        title=title,
        raw_notes=notes_text,
        summary=summary,
        key_decisions=json.dumps(key_decisions),
        tasks_extracted=len(selected_tasks)
    )
    db.session.add(meeting)
    db.session.flush() # To get meeting.id
    
    from app import socketio
    for t in selected_tasks:
        assignee_id = t.get('assigned_to')
        deadline_days = t.get('deadline_days')
        
        deadline = None
        if deadline_days:
            deadline = date.today() + timedelta(days=deadline_days)
            
        task = Task(
            title=t.get('title'),
            description=t.get('description', ''),
            group_id=group.id,
            assigned_to=assignee_id,
            created_by=current_user.id,
            status='todo',
            deadline=deadline
        )
        db.session.add(task)
        db.session.flush()
        
        log_activity(group.id, current_user.id, 'task_created', f"created task: {task.title}", metadata={'task_id': task.id})
        if assignee_id:
            log_activity(group.id, current_user.id, 'task_assigned', f"assigned task: {task.title}", metadata={'task_id': task.id, 'assigned_to': assignee_id})
            
        socketio.emit('task_update', {
            'action': 'created',
            'task': task.to_dict()
        }, room=f'group_{group.id}')
        
    log_activity(group.id, current_user.id, 'meeting_analyzed', f"analyzed meeting: {title}", metadata={'meeting_id': meeting.id})
    db.session.commit()
    
    return jsonify({
        'success': True,
        'tasks_created': len(selected_tasks),
        'meeting_id': meeting.id,
        'redirect_url': url_for('tasks.index', group_id=group.id)
    })

@meetings_bp.route('/<int:meeting_id>')
@login_required
def view(group_id, meeting_id):
    group, role = get_group_and_role(group_id)
    if not group:
        flash("You are not a member of this group.", "danger")
        return redirect(url_for('dashboard.index'))
        
    meeting = MeetingNote.query.filter_by(id=meeting_id, group_id=group.id).first_or_404()
    
    return render_template('meetings/view.html', group=group, current_group_role=role, meeting=meeting)
