from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, abort
from flask_login import login_required, current_user
from app.models.group import Group, GroupMember
from app.models.task import Task
from app.models.activity import ActivityLog
from app.utils.activity import log_activity
from app.utils.decorators import require_role, require_account_type
from app import db

groups_bp = Blueprint('groups', __name__, url_prefix='/groups')

@groups_bp.url_value_preprocessor
def pull_group_id(endpoint, values):
    if values and 'group_id' in values:
        group_id = values.get('group_id')
        if current_user.is_authenticated:
            member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
            if not member:
                abort(403)

@groups_bp.route('/')
@login_required
def index():
    user_groups = GroupMember.query.filter_by(user_id=current_user.id).all()
    group_ids = [m.group_id for m in user_groups]
    groups = Group.query.filter(Group.id.in_(group_ids)).all() if group_ids else []
    
    group_data = []
    for g in groups:
        member_count = g.members.count()
        role = next((m.role for m in user_groups if m.group_id == g.id), 'viewer')
        total_g_tasks = g.tasks.count()
        completed_g_tasks = g.tasks.filter_by(is_completed=True).count()
        progress = (completed_g_tasks / total_g_tasks * 100) if total_g_tasks > 0 else 0
        
        members = g.members.limit(3).all()
        avatars = [m.user.profile_picture for m in members if m.user.profile_picture]
        
        group_data.append({
            'group': g,
            'role': role,
            'member_count': member_count,
            'total_tasks': total_g_tasks,
            'completed_tasks': completed_g_tasks,
            'progress': progress,
            'avatars': avatars
        })
        
    return render_template('groups/index.html', group_data=group_data)

@groups_bp.route('/create', methods=['GET', 'POST'])
@login_required
@require_account_type('mentor', 'team_leader')
def create():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        if not name:
            flash("Group name is required.", "error")
            return redirect(url_for('groups.create'))
            
        group = Group(name=name, description=description, created_by=current_user.id)
        group.generate_invite_code()
        db.session.add(group)
        db.session.flush()
        
        # Creator is auto-added as admin via models hook (after_insert).
        db.session.commit()
        
        log_activity(group.id, current_user.id, 'MEMBER_JOINED', f"created the group.", {})
        
        flash("Group created successfully!", "success")
        return redirect(url_for('groups.dashboard', group_id=group.id))
        
    return render_template('groups/create.html')

@groups_bp.route('/join', methods=['GET', 'POST'])
@login_required
@require_account_type('student')
def join():
    if request.method == 'POST':
        code = request.form.get('invite_code')
        if not code:
            flash("Invite code is required.", "error")
            return redirect(url_for('groups.join'))
            
        group = Group.query.filter_by(invite_code=code.upper()).first()
        if not group:
            flash("Invalid invite code.", "error")
            return redirect(url_for('groups.join'))
            
        member = GroupMember.query.filter_by(group_id=group.id, user_id=current_user.id).first()
        if member:
            flash("You are already a member of this group.", "info")
            return redirect(url_for('groups.dashboard', group_id=group.id))
            
        new_member = GroupMember(group_id=group.id, user_id=current_user.id, role='editor')
        db.session.add(new_member)
        db.session.commit()
        
        log_activity(group.id, current_user.id, 'MEMBER_JOINED', f"joined via invite code.", {})
        
        from app.tasks.email_tasks import send_member_joined_email
        send_member_joined_email.delay(new_user_id=current_user.id, group_id=group.id)
        
        flash("Successfully joined the group!", "success")
        return redirect(url_for('groups.dashboard', group_id=group.id))
        
    return render_template('groups/join.html')

@groups_bp.route('/<int:group_id>')
@login_required
def dashboard(group_id):
    group = Group.query.get_or_404(group_id)
    members = group.members.all()
    tasks = group.tasks.order_by(Task.created_at.desc()).limit(5).all()
    activities = ActivityLog.query.filter_by(group_id=group_id).order_by(ActivityLog.created_at.desc()).limit(10).all()
    
    completed_tasks = group.tasks.filter_by(is_completed=True).count()
    
    from app.utils.time_tracking import calculate_member_time_stats
    from datetime import datetime, timedelta, timezone
    
    time_stats = calculate_member_time_stats(group_id)
    
    # Calculate for "This Week"
    today = datetime.now(timezone.utc).date()
    start_of_week = today - timedelta(days=today.weekday())
    this_week_stats = calculate_member_time_stats(group_id, start_date=start_of_week)
    top_3_this_week = this_week_stats.get('by_member', [])[:3]
    
    return render_template('groups/dashboard.html', 
        group=group, 
        members=members, 
        tasks=tasks, 
        activities=activities,
        completed_tasks=completed_tasks,
        time_stats=time_stats,
        top_3_this_week=top_3_this_week
    )

@groups_bp.route('/<int:group_id>/settings', methods=['GET', 'POST'])
@login_required
@require_role('admin')
def settings(group_id):
    group = Group.query.get_or_404(group_id)
    if request.method == 'POST':
        group.name = request.form.get('name')
        group.description = request.form.get('description')
        db.session.commit()
        flash("Group settings updated.", "success")
        return redirect(url_for('groups.settings', group_id=group_id))
        
    return render_template('groups/settings.html', group=group)

@groups_bp.route('/<int:group_id>/leave', methods=['POST'])
@login_required
def leave(group_id):
    group = Group.query.get_or_404(group_id)
    member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    
    if member.role == 'admin':
        admins = GroupMember.query.filter_by(group_id=group_id, role='admin').count()
        if admins <= 1:
            flash("You are the only admin. You must promote someone else before leaving.", "error")
            return redirect(url_for('groups.settings', group_id=group_id))
            
    db.session.delete(member)
    db.session.commit()
    
    log_activity(group_id, current_user.id, 'MEMBER_LEFT', f"left the group.", {})
    flash("You have left the group.", "success")
    return redirect(url_for('dashboard.index'))

@groups_bp.route('/<int:group_id>/remove-member/<int:user_id>', methods=['POST'])
@login_required
@require_role('admin')
@require_account_type('mentor')
def remove_member(group_id, user_id):
    if user_id == current_user.id:
        return jsonify({'success': False, 'message': 'Cannot remove yourself directly.'})
        
    member = GroupMember.query.filter_by(group_id=group_id, user_id=user_id).first_or_404()
    db.session.delete(member)
    db.session.commit()
    
    log_activity(group_id, user_id, 'MEMBER_LEFT', f"was removed from the group.", {})
    return jsonify({'success': True})

@groups_bp.route('/<int:group_id>/change-role/<int:user_id>', methods=['POST'])
@login_required
@require_role('admin')
@require_account_type('mentor')
def change_role(group_id, user_id):
    # Support both normal form/json formats
    new_role = request.json.get('new_role') if request.is_json else request.form.get('new_role')
    
    if new_role not in ['admin', 'editor', 'viewer']:
        return jsonify({'success': False, 'message': 'Invalid role.'})
        
    member = GroupMember.query.filter_by(group_id=group_id, user_id=user_id).first_or_404()
    
    if member.role == 'admin' and new_role != 'admin':
        admins = GroupMember.query.filter_by(group_id=group_id, role='admin').count()
        if admins <= 1:
            return jsonify({'success': False, 'message': 'Cannot demote the last admin.'})
            
    member.role = new_role
    db.session.commit()
    
    log_activity(group_id, current_user.id, 'ROLE_CHANGED', f"changed \u007bmember.user.username\u007d's role to \u007bnew_role\u007d.", {'target_user_id': user_id, 'new_role': new_role})
    return jsonify({'success': True})

@groups_bp.route('/<int:group_id>/members')
@login_required
def members(group_id):
    group = Group.query.get_or_404(group_id)
    return render_template('groups/members.html', group=group)

@groups_bp.route('/<int:group_id>/invite')
@login_required
@require_role('editor')
def invite(group_id):
    return redirect(url_for('groups.members', group_id=group_id))

@groups_bp.route('/<int:group_id>/regenerate-invite', methods=['POST'])
@login_required
@require_role('admin')
def regenerate_invite(group_id):
    group = Group.query.get_or_404(group_id)
    group.generate_invite_code()
    db.session.commit()
    return jsonify({'success': True, 'new_code': group.invite_code})
