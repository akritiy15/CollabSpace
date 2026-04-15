from app import db, mail
from celery_worker import celery
from flask import render_template, current_app, url_for
from flask_mail import Message
from datetime import datetime, timedelta, timezone
from app.models.task import Task
from app.models.user import User
from app.models.group import Group, GroupMember
from app.models.activity import ActivityLog
from app.models.notification import UserNotificationPrefs

def get_user_prefs(user_id):
    prefs = UserNotificationPrefs.query.filter_by(user_id=user_id).first()
    if not prefs:
        prefs = UserNotificationPrefs(user_id=user_id)
        db.session.add(prefs)
        db.session.commit()
    return prefs

@celery.task(name='tasks.send_task_assignment_email', bind=True, max_retries=3, default_retry_delay=60)
def send_task_assignment_email(self, user_id, task_id, assigner_id, group_id):
    try:
        user = db.session.get(User, user_id)
        prefs = get_user_prefs(user_id)
        if not prefs.task_assignment_emails:
            return  # User opted out

        task = db.session.get(Task, task_id)
        assigner = db.session.get(User, assigner_id)
        group = db.session.get(Group, group_id)

        if not all([user, task, assigner, group]):
            return

        with current_app.test_request_context():
            html = render_template(
                'emails/task_assigned.html',
                username=user.username,
                assigner_name=assigner.username,
                group_name=group.name,
                task_title=task.title,
                task_description=task.description,
                deadline=task.deadline,
                current_date=datetime.now().date(),
                task_url=url_for('tasks.index', group_id=group.id, _external=True),
                assigned_date=datetime.now().strftime('%B %d, %Y')
            )
            
        msg = Message(
            subject='You have been assigned a task',
            recipients=[user.email],
            html=html
        )
        mail.send(msg)
    except Exception as exc:
        self.retry(exc=exc)


@celery.task(name='tasks.send_deadline_reminder')
def send_deadline_reminder_email(user_id, task_id):
    user = db.session.get(User, user_id)
    prefs = get_user_prefs(user_id)
    if not prefs.deadline_reminder_emails:
        return

    task = db.session.get(Task, task_id)
    if not task or task.is_completed:
        return

    with current_app.test_request_context():
        html = render_template(
            'emails/deadline_reminder.html',
            username=user.username,
            group_name=task.group.name,
            task_title=task.title,
            deadline=task.deadline,
            task_status=task.status,
            task_url=url_for('tasks.index', group_id=task.group_id, _external=True)
        )

    msg = Message(
        subject=f'Task deadline approaching — {task.title}',
        recipients=[user.email],
        html=html
    )
    mail.send(msg)


@celery.task(name='tasks.check_upcoming_deadlines')
def check_upcoming_deadlines():
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    
    # Tasks due within next 24 hours that haven't had a reminder sent yet
    tasks = Task.query.filter(
        Task.is_completed == False,
        Task.assigned_to != None,
        Task.deadline >= now.date(),
        Task.deadline <= tomorrow.date(),
        db.or_(Task.reminder_sent == False, Task.reminder_sent == None)
    ).all()
    
    for task in tasks:
        send_deadline_reminder_email.delay(task.assigned_to, task.id)
        task.reminder_sent = True
        
    db.session.commit()


@celery.task(name='tasks.send_weekly_report')
def send_weekly_report_email(group_id):
    group = db.session.get(Group, group_id)
    if not group: return
    
    admins = GroupMember.query.filter_by(group_id=group_id, role='admin').all()
    if not admins: return
    
    now = datetime.now()
    last_week = now - timedelta(days=7)
    
    # Stats
    tasks_created = Task.query.filter(Task.group_id==group_id, Task.created_at >= last_week).count()
    
    # In SQLite, checking completed_at might fail if it's NULL, so handle logic cautiously.
    tasks_completed = Task.query.filter(
        Task.group_id==group_id, 
        Task.is_completed==True,
        Task.completed_at >= last_week
    ).count()
    
    new_members = GroupMember.query.filter(GroupMember.group_id==group_id, GroupMember.joined_at >= last_week).count()
    
    stats = {
        'tasks_created': tasks_created,
        'tasks_completed': tasks_completed,
        'new_members': new_members
    }
    
    # Top performer
    # Complex query simulated due to DB abstraction
    completed_this_week = Task.query.filter(
        Task.group_id==group_id, Task.is_completed==True, Task.completed_at >= last_week
    ).all()
    
    counts = {}
    for t in completed_this_week:
        if t.assigned_to:
            counts[t.assigned_to] = counts.get(t.assigned_to, 0) + 1
            
    top_performer = None
    if counts:
        best_id = max(counts, key=counts.get)
        b_user = db.session.get(User, best_id)
        if b_user:
            top_performer = {
                'username': b_user.username,
                'completed_count': counts[best_id]
            }
            
    recent_activity = ActivityLog.query.filter_by(group_id=group_id).order_by(ActivityLog.created_at.desc()).limit(5).all()
    date_range = f"{last_week.strftime('%b %d')} - {now.strftime('%b %d')}"
    
    for admin_member in admins:
        user = admin_member.user
        prefs = get_user_prefs(user.id)
        if not prefs.weekly_summary_emails:
            continue
            
        with current_app.test_request_context():
            html = render_template(
                'emails/weekly_report.html',
                username=user.username,
                group_name=group.name,
                date_range=date_range,
                stats=stats,
                top_performer=top_performer,
                recent_activity=recent_activity,
                report_url=url_for('reports.preview', group_id=group.id, _external=True)
            )
            
        msg = Message(
            subject=f'Weekly Summary — {group.name}',
            recipients=[user.email],
            html=html
        )
        mail.send(msg)


@celery.task(name='tasks.send_weekly_reports_all_groups')
def send_weekly_reports_all_groups():
    groups = Group.query.all()
    for g in groups:
        send_weekly_report_email.delay(g.id)


@celery.task(name='tasks.send_member_joined')
def send_member_joined_email(new_user_id, group_id):
    new_user = db.session.get(User, new_user_id)
    group = db.session.get(Group, group_id)
    
    if not new_user or not group: return
    
    admins = GroupMember.query.filter_by(group_id=group_id, role='admin').all()
    member_count = group.members.count()
    
    for admin_member in admins:
        # Don't send email to the person who joined if they are somehow the admin
        if admin_member.user_id == new_user_id:
            continue
            
        user = admin_member.user
        prefs = get_user_prefs(user.id)
        if not prefs.member_joined_emails:
            continue
            
        with current_app.test_request_context():
            html = render_template(
                'emails/member_joined.html',
                admin_username=user.username,
                new_member=new_user.username,
                group_name=group.name,
                join_date=datetime.now().strftime('%B %d, %Y'),
                member_count=member_count,
                group_url=url_for('groups.dashboard', group_id=group.id, _external=True)
            )
            
        msg = Message(
            subject=f'{new_user.username} joined your group',
            recipients=[user.email],
            html=html
        )
        mail.send(msg)
