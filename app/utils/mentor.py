import datetime
from app import db
from app.models.group import Group, GroupMember
from app.models.task import Task
from app.models.activity import ActivityLog
from app.models.user import User
from app.utils.report import calculate_report_data
from sqlalchemy import desc

def get_relative_time(dt):
    if not dt:
        return "Never"
    
    # Ensure dt is timezone-aware and converted to UTC for comparison if necessary,
    # but let's assume it's UTC naive or aware and compare with utcnow.
    now = datetime.datetime.utcnow()
    # Normalize naive/aware
    if dt.tzinfo:
        now = datetime.datetime.now(datetime.timezone.utc)
        
    diff = now - dt
    days = diff.days
    
    if days == 0:
        return "Today"
    elif days == 1:
        return "Yesterday"
    else:
        return f"{days} days ago"

def get_mentor_overview(user_id):
    admin_memberships = GroupMember.query.filter_by(user_id=user_id, role='admin').all()
    groups_data = []
    all_mentor_tasks = []
    
    total_students = set()
    healthy_count = 0
    at_risk_count = 0
    critical_count = 0
    
    for membership in admin_memberships:
        group = membership.group
        # IMPORT AND REUSE REPORt CALCULATION!
        report_data = calculate_report_data(group)
        
        # Student members are non-admin
        student_members = [m for m in group.members if m.role != 'admin']
        for sm in student_members:
            total_students.add(sm.user_id)
            
        health_score = report_data['health']['score']
        health_status = report_data['health']['status']
        
        if health_score >= 80:
            health_color = '#27AE60'
            healthy_count += 1
        elif health_score >= 50:
            health_color = '#F39C12'
            at_risk_count += 1
        else:
            health_color = '#E74C3C'
            critical_count += 1

        recent_activity = ActivityLog.query.filter_by(group_id=group.id).order_by(desc(ActivityLog.created_at)).first()
        last_activity_dt = recent_activity.created_at if recent_activity else None
        
        recent_tasks_qs = Task.query.filter_by(group_id=group.id).order_by(desc(Task.created_at)).limit(3).all()
        recent_tasks = [{
            'title': t.title,
            'status': t.status,
            'assigned_to_username': t.assignee.username if t.assignee else 'Unassigned'
        } for t in recent_tasks_qs]
        
        # Collect all tasks for the Task Overview dashboard
        for task in group.tasks.all():
            task_time_stats = None
            for tk in report_data['time_stats'].get('by_task', []):
                if tk.get('task_id') == task.id:
                    task_time_stats = tk
                    break
                    
            all_mentor_tasks.append({
                'group_name': group.name,
                'group_id': group.id,
                'task': task,
                'time_stats': task_time_stats
            })
            
        groups_data.append({
            'id': group.id,
            'name': group.name,
            'description': group.description,
            'student_members': [{'username': m.user.username} for m in student_members],
            'total_tasks': report_data['overall']['total_tasks'],
            'completed_tasks': report_data['overall']['completed_tasks'],
            'overdue_tasks': report_data['overall']['tasks_overdue_count'],
            'completion_rate': report_data['health']['completion_rate'],
            'health_score': health_score,
            'health_status': health_status,
            'health_color': health_color,
            'last_activity': last_activity_dt,
            'last_activity_relative': get_relative_time(last_activity_dt),
            'recent_tasks': recent_tasks,
            'recent_activity': [{
                 'description': a.description,
                 'created_at': a.created_at,
                 'relative_time': get_relative_time(a.created_at)
            } for a in ActivityLog.query.filter_by(group_id=group.id).order_by(desc(ActivityLog.created_at)).limit(3).all()],
            'time_logged_minutes': report_data['time_stats'].get('total_minutes', 0),
            'meeting_notes_count': 0  # MeetingNote model does not exist yet
        })
        
    # Sort by health_score ascending (Critical first)
    groups_data.sort(key=lambda x: x['health_score'])
    
    # Sort tasks by deadline or created_at
    all_mentor_tasks.sort(key=lambda x: (x['task'].deadline is None, x['task'].deadline or x['task'].created_at))
    
    return {
        'total_groups': len(groups_data),
        'healthy_count': healthy_count,
        'at_risk_count': at_risk_count,
        'critical_count': critical_count,
        'total_students': len(total_students),
        'groups': groups_data,
        'all_tasks': all_mentor_tasks
    }

def get_group_student_detail(group_id, mentor_user_id):
    # Validate mentor is admin
    membership = GroupMember.query.filter_by(group_id=group_id, user_id=mentor_user_id, role='admin').first()
    if not membership:
        return None
        
    group = membership.group
    report_data = calculate_report_data(group)
    
    students = []
    # students: list of non-admin members with: username, profile_picture, tasks_assigned, tasks_completed, completion_rate, time_logged_minutes, time_logged_formatted
    for mp in report_data['member_performance']:
        # check if this user is non-admin
        mem = GroupMember.query.filter_by(group_id=group.id, user_id=mp['user'].id).first()
        if mem and mem.role != 'admin':
            # Extract time logged from report_data['time_stats']
            user_time = 0
            for tm in report_data['time_stats'].get('by_member', []):
                if tm.get('username') == mp['user'].username:
                    user_time = tm.get('total_minutes', 0)
                    break
            
            h = user_time // 60
            m = user_time % 60
            time_formatted = f"{int(h)}h {int(m)}m" if user_time else "0h 0m"
            
            students.append({
                'username': mp['user'].username,
                'profile_picture': mp['user'].profile_picture,
                'tasks_assigned': mp['assigned'],
                'tasks_completed': mp['completed'],
                'completion_rate': mp['completion_rate'],
                'time_logged_minutes': user_time,
                'time_logged_formatted': time_formatted
            })
            
    recent_activities = ActivityLog.query.filter_by(group_id=group.id).order_by(desc(ActivityLog.created_at)).limit(20).all()
    
    all_tasks = group.tasks.all()
    
    def severity_score(task):
        status = task.deadline_status
        if status == 'overdue': return 0
        if status == 'critical': return 1
        if status == 'warning': return 2
        return 3
        
    all_tasks.sort(key=severity_score)
    
    return {
        'group': group,
        'students': students,
        'all_tasks': all_tasks,
        'meeting_notes': [], # MeetingNote does not exist
        'activity_log': recent_activities,
        'health_score': report_data['health']['score'],
        'health_status': report_data['health']['status'],
        'time_stats': report_data['time_stats']
    }
