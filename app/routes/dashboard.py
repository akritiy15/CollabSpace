from flask import Blueprint, render_template, request, jsonify, redirect
from flask_login import login_required, current_user
from app.models.group import Group, GroupMember
from app.models.activity import ActivityLog
from app.models.connection import MemberConnection
from app.models.task import Task
from app.models.meeting import MeetingNote
from datetime import datetime
from app import db
from sqlalchemy import or_

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@dashboard_bp.route('/')
@login_required
def index():
    if current_user.account_type == 'mentor' or getattr(current_user, 'mentor_profile', None):
        return redirect('/mentor/dashboard')
        
    user_groups = GroupMember.query.filter_by(user_id=current_user.id).all()
    group_ids = [m.group_id for m in user_groups]
    groups = Group.query.filter(Group.id.in_(group_ids)).all() if group_ids else []
    
    hour = datetime.now().hour
    if hour < 12: greeting = "Good morning"
    elif hour < 18: greeting = "Good afternoon"
    else: greeting = "Good evening"

    if current_user.account_type == 'team_leader':
        led_groups = [g for g in groups if next((m.role for m in user_groups if m.group_id == g.id), 'viewer') == 'admin']
        led_group_ids = [g.id for g in led_groups]
        
        total_tasks_created = Task.query.filter_by(created_by=current_user.id).count()
        team_members = db.session.query(GroupMember.user_id).filter(GroupMember.group_id.in_(led_group_ids)).distinct().count() if led_group_ids else 0
        tasks_pending_approval = Task.query.filter(Task.group_id.in_(led_group_ids), getattr(Task, 'approval_status', '') == 'pending').all() if led_group_ids else []
        
        activities = ActivityLog.query.filter(ActivityLog.group_id.in_(led_group_ids)).order_by(ActivityLog.created_at.desc()).limit(15).all() if led_group_ids else []
        
        group_data = []
        for g in led_groups:
            member_count = g.members.count()
            total_g_tasks = g.tasks.count()
            completed_g_tasks = g.tasks.filter_by(is_completed=True).count()
            progress = (completed_g_tasks / total_g_tasks * 100) if total_g_tasks > 0 else 0
            
            pending_g_tasks = g.tasks.filter(getattr(Task, 'approval_status', '') == 'pending').count()
            
            members = g.members.limit(3).all()
            avatars = [m.user.profile_picture for m in members if m.user.profile_picture]
            
            group_data.append({
                'group': g, 'member_count': member_count, 'total_tasks': total_g_tasks,
                'completed_tasks': completed_g_tasks, 'progress': progress, 
                'pending_approvals': pending_g_tasks, 'avatars': avatars
            })
            
        return render_template('dashboard/team_leader.html',
            greeting=greeting, group_data=group_data, total_tasks_created=total_tasks_created,
            team_members=team_members, pending_approvals=tasks_pending_approval, activities=activities)
            
    else: # student
        my_tasks = Task.query.filter_by(assigned_to=current_user.id).all()
        # stats
        assigned_count = len(my_tasks)
        completed_count = sum(1 for t in my_tasks if t.is_completed)
        
        now = datetime.now()
        upcoming_tasks = [t for t in my_tasks if t.deadline and not t.is_completed and (t.deadline - now).days <= 7]
        
        # time logged
        from app.models.time_tracking import TimeLog
        from datetime import timedelta
        this_week_start = (now - timedelta(days=now.weekday())).date()
        this_week_logs = TimeLog.query.filter(
            TimeLog.user_id == current_user.id,
            TimeLog.logged_date >= this_week_start
        ).order_by(TimeLog.logged_date.desc()).all()
        
        from app.utils.time_tracking import minutes_to_formatted
        hours_logged_this_week = minutes_to_formatted(sum(l.duration_minutes for l in this_week_logs))
        
        # performance stats
        on_time_count = sum(1 for t in my_tasks if t.is_completed and t.deadline and t.deadline.date() >= (t.completed_at or now).date())
        on_time_count += sum(1 for t in my_tasks if t.is_completed and not t.deadline)
        
        completion_rate = round((completed_count / assigned_count * 100) if assigned_count > 0 else 0)
        on_time_rate = round((on_time_count / completed_count * 100) if completed_count > 0 else 100)
        
        total_time_minutes = sum(l.duration_minutes for l in TimeLog.query.filter_by(user_id=current_user.id).all())
        total_hours = minutes_to_formatted(total_time_minutes)
        
        score = (completion_rate * 0.4) + ((on_time_rate * 0.25) if completed_count > 0 else (15 / 25 * 100 * 0.25)) + 15 + 9 # approx for meeting/activity
        grade = 'F'
        if score >= 90: grade = 'A'
        elif score >= 80: grade = 'B'
        elif score >= 70: grade = 'C'
        elif score >= 60: grade = 'D'
        
        stats = {
            'assigned': assigned_count, 'completed': completed_count,
            'hours_week': hours_logged_this_week, 'upcoming': len(upcoming_tasks),
            'comp_rate': completion_rate, 'ontime_rate': on_time_rate,
            'total_hours': total_hours, 'grade': grade
        }
        
        return render_template('dashboard/student.html',
            greeting=greeting, stats=stats, my_tasks=my_tasks, time_logs=this_week_logs, now=datetime.utcnow)

@dashboard_bp.route('/api/search')
@login_required
def global_search():
    query_str = request.args.get('q', '').strip()
    if len(query_str) < 2:
        return jsonify({'results': []})
        
    term = f"%{query_str}%"
    results = []
    
    # Restrict to user's memberships
    user_groups = GroupMember.query.filter_by(user_id=current_user.id).all()
    group_ids = [m.group_id for m in user_groups]
    
    # 1. Search Groups (where user is member)
    if group_ids:
        matched_groups = Group.query.filter(
            Group.id.in_(group_ids),
            Group.name.ilike(term)
        ).limit(5).all()
        for g in matched_groups:
            results.append({
                'type': 'group',
                'title': g.name,
                'subtitle': 'Group',
                'url': f'/groups/{g.id}'
            })
            
        # 2. Search Tasks in these groups
        matched_tasks = Task.query.filter(
            Task.group_id.in_(group_ids),
            Task.title.ilike(term)
        ).limit(5).all()
        for t in matched_tasks:
            results.append({
                'type': 'task',
                'title': t.title,
                'subtitle': f'Task in {t.group.name}',
                'url': f'/groups/{t.group_id}'
            })
            
    return jsonify({'results': results})
