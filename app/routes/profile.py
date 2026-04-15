import os
import uuid
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models.user import User
from app.models.group import GroupMember
from app.models.connection import MemberConnection
from app.models.notification import UserNotificationPrefs
from sqlalchemy import or_

profile_bp = Blueprint('profile', __name__, url_prefix='/profile')

def get_connections(user_id):
    connections = MemberConnection.query.filter(
        MemberConnection.status == 'accepted',
        or_(MemberConnection.sender_id == user_id, MemberConnection.receiver_id == user_id)
    ).all()
    friends = []
    for f in connections:
        if f.sender_id == user_id:
            friends.append(f.receiver)
        else:
            friends.append(f.sender)
    return friends

@profile_bp.route('/')
@login_required
def index():
    friends = get_connections(current_user.id)
    group_count = GroupMember.query.filter_by(user_id=current_user.id).count()
    
    project_times = []
    if current_user.account_type == 'student':
        from app.models.time_tracking import TimeLog
        from app.utils.time_tracking import minutes_to_formatted
        from sqlalchemy import func
        from app.models.group import Group
        
        results = db.session.query(
            TimeLog.group_id,
            func.sum(TimeLog.duration_minutes).label('total_minutes')
        ).filter(TimeLog.user_id == current_user.id).group_by(TimeLog.group_id).all()
        
        for g_id, mins in results:
            g = Group.query.get(g_id)
            if g:
                project_times.append({
                    'group_name': g.name,
                    'group_id': g.id,
                    'minutes': mins,
                    'formatted': minutes_to_formatted(mins)
                })
                
    user_tasks = []
    user_scores = []
    academic_profile = None
    if current_user.account_type == 'student':
        from app.models.task import Task
        from app.models.score import StudentScore
        from app.models.profile import StudentAcademicProfile
        user_tasks = Task.query.filter_by(assigned_to=current_user.id).order_by(db.desc(Task.deadline)).all()
        user_scores = StudentScore.query.filter_by(student_id=current_user.id).order_by(db.desc(StudentScore.calculated_at)).all()
        academic_profile = StudentAcademicProfile.query.filter_by(user_id=current_user.id).first()
                
    return render_template('profile/index.html', user=current_user, friends=friends, group_count=group_count, project_times=project_times, user_tasks=user_tasks, user_scores=user_scores, academic_profile=academic_profile)

@profile_bp.route('/edit', methods=['POST'])
@login_required
def edit():
    username = request.form.get('username')
    bio = request.form.get('bio')
    
    if username and username != current_user.username:
        if User.query.filter_by(username=username).first():
            flash("Username is already taken.", "error")
            return redirect(url_for('profile.index'))
        current_user.username = username
        
    current_user.bio = bio
    db.session.commit()
    flash("Profile updated successfully.", "success")
    return redirect(url_for('profile.index'))

@profile_bp.route('/avatar', methods=['POST'])
@login_required
def avatar():
    if 'avatar' not in request.files:
        return jsonify({'success': False, 'message': 'No file part'})
        
    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No selected file'})
        
    allowed_exts = {'png', 'jpg', 'jpeg', 'gif'}
    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if ext not in allowed_exts:
        return jsonify({'success': False, 'message': 'Invalid file type. Must be jpg, png, or gif.'})
        
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > 2 * 1024 * 1024:
        return jsonify({'success': False, 'message': 'File too large (max 2MB).'})
        
    uploads_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'avatars')
    os.makedirs(uploads_dir, exist_ok=True)
    
    filename = secure_filename(f"{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}")
    filepath = os.path.join(uploads_dir, filename)
    file.save(filepath)
    
    avatar_url = url_for('static', filename=f"uploads/avatars/{filename}")
    current_user.profile_picture = avatar_url
    db.session.commit()
    
    return jsonify({'success': True, 'avatar_url': avatar_url})

@profile_bp.route('/<username>')
@login_required
def view(username):
    user = User.query.filter_by(username=username).first_or_404()
    if user.id == current_user.id:
        return redirect(url_for('profile.index'))
        
    friends = get_connections(user.id)
    group_count = GroupMember.query.filter_by(user_id=user.id).count()
    
    req = MemberConnection.query.filter(
        or_(
            (MemberConnection.sender_id == current_user.id) & (MemberConnection.receiver_id == user.id),
            (MemberConnection.sender_id == user.id) & (MemberConnection.receiver_id == current_user.id)
        )
    ).first()
    
    connection_status = 'none'
    if req:
        if req.status == 'accepted':
            connection_status = 'connected'
        elif req.sender_id == current_user.id:
            connection_status = 'pending_sent'
        else:
            connection_status = 'pending_received'
            
    user_groups = set([m.group_id for m in GroupMember.query.filter_by(user_id=user.id)])
    my_groups = set([m.group_id for m in GroupMember.query.filter_by(user_id=current_user.id)])
    mutual_group_ids = list(user_groups.intersection(my_groups))
    
    user_tasks = []
    user_scores = []
    project_times = []
    academic_profile = None
    if user.account_type == 'student':
        from app.models.task import Task
        from app.models.score import StudentScore
        from app.models.profile import StudentAcademicProfile
        from app.models.time_tracking import TimeLog
        from app.utils.time_tracking import minutes_to_formatted
        from sqlalchemy import func
        from app.models.group import Group
        
        user_tasks = Task.query.filter_by(assigned_to=user.id).order_by(db.desc(Task.deadline)).all()
        user_scores = StudentScore.query.filter_by(student_id=user.id).order_by(db.desc(StudentScore.calculated_at)).all()
        academic_profile = StudentAcademicProfile.query.filter_by(user_id=user.id).first()
        
        results = db.session.query(
            TimeLog.group_id,
            func.sum(TimeLog.duration_minutes).label('total_minutes')
        ).filter(TimeLog.user_id == user.id).group_by(TimeLog.group_id).all()
        for g_id, mins in results:
            g = Group.query.get(g_id)
            if g:
                project_times.append({
                    'group_name': g.name,
                    'group_id': g.id,
                    'formatted': minutes_to_formatted(mins)
                })
    
    return render_template('profile/view.html', 
        target_user=user, 
        friends=friends, 
        group_count=group_count,
        connection_status=connection_status,
        mutual_count=len(mutual_group_ids),
        user_tasks=user_tasks,
        user_scores=user_scores,
        project_times=project_times,
        academic_profile=academic_profile
    )

@profile_bp.route('/notifications', methods=['GET', 'POST'])
@login_required
def notifications():
    prefs = UserNotificationPrefs.query.filter_by(user_id=current_user.id).first()
    if not prefs:
        prefs = UserNotificationPrefs(user_id=current_user.id)
        db.session.add(prefs)
        db.session.commit()
        
    if request.method == 'POST':
        # Assume request is JSON
        data = request.json
        if data:
            if 'task_assignment_emails' in data:
                prefs.task_assignment_emails = data['task_assignment_emails']
            if 'deadline_reminder_emails' in data:
                prefs.deadline_reminder_emails = data['deadline_reminder_emails']
            if 'weekly_summary_emails' in data:
                prefs.weekly_summary_emails = data['weekly_summary_emails']
            if 'member_joined_emails' in data:
                prefs.member_joined_emails = data['member_joined_emails']
            db.session.commit()
            return jsonify({'success': True})
            
    return render_template('profile/notifications.html', prefs=prefs)

@profile_bp.route('/api/profile/academic', methods=['POST'])
@login_required
def update_academic():
    if current_user.account_type != 'student':
        return jsonify({'success': False, 'message': 'Only students have academic profiles'})
    
    from app.models.profile import StudentAcademicProfile
    
    # Can be form data or json
    data = request.form
    
    profile = StudentAcademicProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        profile = StudentAcademicProfile(user_id=current_user.id)
        db.session.add(profile)
        
    profile.institution = data.get('institution')
    profile.branch = data.get('branch')
    
    sem = data.get('semester')
    profile.semester = int(sem) if sem and sem.isdigit() else None
    
    ay = data.get('admission_year')
    profile.admission_year = int(ay) if ay and ay.isdigit() else None
    
    profile.enrollment_number = data.get('enrollment_number')
    profile.linkedin_url = data.get('linkedin_url')
    profile.github_url = data.get('github_url')
    
    hours = data.get('availability_hours_per_week')
    profile.availability_hours_per_week = int(hours) if hours and hours.isdigit() else None
    
    db.session.commit()
    return jsonify({'success': True})

@profile_bp.route('/api/notifications', methods=['GET'])
@login_required
def get_notifications():
    from app.models.notification import Notification
    from flask import jsonify
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(db.desc(Notification.created_at)).limit(20).all()
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({
        'notifications': [n.to_dict() for n in notifs],
        'unread_count': unread_count
    })

@profile_bp.route('/api/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    from app.models.notification import Notification
    from flask import jsonify
    notif = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first()
    if notif:
        notif.is_read = True
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False}), 404
