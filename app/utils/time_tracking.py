import re
from datetime import datetime, timezone
from collections import defaultdict
from app import db
from app.models.time_tracking import TimeLog, TaskEstimate
from app.models.group import Group, GroupMember
from app.models.task import Task
from sqlalchemy import func

def minutes_to_formatted(minutes):
    if not minutes or minutes == 0:
        return "0m"
    
    hours, mins = divmod(minutes, 60)
    
    if hours > 0 and mins > 0:
        return f"{int(hours)}h {int(mins)}m"
    elif hours > 0:
        return f"{int(hours)}h"
    else:
        return f"{int(mins)}m"

def formatted_to_minutes(formatted_string):
    if not formatted_string:
        return 0
        
    s = str(formatted_string).strip().lower()
    
    # Just a number e.g. "90"
    if s.replace('.', '', 1).isdigit():
        return int(float(s))
        
    # Match "1.5h"
    h_only = re.match(r"^([\d\.]+)h$", s)
    if h_only:
        return int(float(h_only.group(1)) * 60)
        
    # Match "30m"
    m_only = re.match(r"^(\d+)m$", s)
    if m_only:
        return int(m_only.group(1))
        
    # Match "2h 30m"
    hm_mixed = re.match(r"^(\d+)h\s*(\d+)m$", s)
    if hm_mixed:
        h = int(hm_mixed.group(1))
        m = int(hm_mixed.group(2))
        return h * 60 + m
        
    raise ValueError("Unrecognized time format. Must be e.g. '2h 30m', '1.5h', '30m' or '90'.")

def calculate_member_time_stats(group_id, user_id=None, start_date=None, end_date=None):
    query = TimeLog.query.filter_by(group_id=group_id)
    
    if user_id is not None:
        query = query.filter_by(user_id=user_id)
        
    if start_date:
        query = query.filter(TimeLog.logged_date >= start_date)
    if end_date:
        query = query.filter(TimeLog.logged_date <= end_date)
        
    logs = query.all()
    
    total_minutes = sum(log.duration_minutes for log in logs)
    
    # By task stats
    task_map = defaultdict(lambda: {'task_obj': None, 'minutes': 0})
    for log in logs:
        task_map[log.task_id]['task_obj'] = log.task
        task_map[log.task_id]['minutes'] += log.duration_minutes
        
    by_task = []
    
    # Get all task estimates to avoid N+1 queries if possible, but task_obj.estimated_minutes property already hits db
    for tid, tdata in task_map.items():
        task = tdata['task_obj']
        mins = tdata['minutes']
        
        est = task.estimated_minutes
        variance = est - mins if est is not None else None
        
        if est is None:
            v_status = 'no_estimate'
        elif variance > 0:
            v_status = 'under'
        elif variance < 0:
            v_status = 'over'
        else:
            v_status = 'on_track'
            
        by_task.append({
            'task_id': task.id,
            'task_title': task.title,
            'task_status': task.status,
            'minutes_logged': mins,
            'formatted': minutes_to_formatted(mins),
            'estimated_minutes': est,
            'estimated_formatted': minutes_to_formatted(est) if est is not None else None,
            'variance_minutes': variance,
            'variance_formatted': minutes_to_formatted(abs(variance)) if variance is not None else None,
            'variance_status': v_status,
            'percentage_of_total': round((mins / total_minutes * 100), 1) if total_minutes > 0 else 0
        })
        
    by_task.sort(key=lambda x: x['minutes_logged'], reverse=True)
    most_logged_task = by_task[0] if by_task else None
    
    # By date stats
    date_map = defaultdict(int)
    for log in logs:
        date_map[log.logged_date] += log.duration_minutes
        
    by_date = []
    for d, m in sorted(date_map.items()):
        by_date.append({
            'date': d.isoformat(),
            'minutes': m,
            'formatted': minutes_to_formatted(m)
        })
        
    busiest_day = max(by_date, key=lambda x: x['minutes']) if by_date else None
    
    # Calculate daily average based on date span of logs, or just unique days
    unique_days = len(date_map)
    daily_average = round(total_minutes / unique_days) if unique_days > 0 else 0

    stats = {
        'total_minutes': total_minutes,
        'total_formatted': minutes_to_formatted(total_minutes),
        'by_task': by_task,
        'by_date': by_date,
        'busiest_day': busiest_day,
        'daily_average': daily_average,
        'most_logged_task': most_logged_task,
        'unique_days_tracked': unique_days,
        'tasks_tracked_count': len(by_task)
    }
    
    if user_id is None:
        user_map = defaultdict(lambda: {'user_obj': None, 'minutes': 0, 'tasks': set()})
        for log in logs:
            user_map[log.user_id]['user_obj'] = log.user
            user_map[log.user_id]['minutes'] += log.duration_minutes
            user_map[log.user_id]['tasks'].add(log.task_id)
            
        by_member = []
        for uid, udata in user_map.items():
            user = udata['user_obj']
            u_mins = udata['minutes']
            by_member.append({
                'user_id': user.id,
                'username': user.username,
                'profile_picture': getattr(user, 'profile_picture', None),
                'total_minutes': u_mins,
                'formatted': minutes_to_formatted(u_mins),
                'task_count': len(udata['tasks']),
                'percentage_of_total': round((u_mins / total_minutes * 100), 1) if total_minutes > 0 else 0
            })
        by_member.sort(key=lambda x: x['total_minutes'], reverse=True)
        stats['by_member'] = by_member
        stats['most_active_member'] = by_member[0] if by_member else None
        
    return stats
