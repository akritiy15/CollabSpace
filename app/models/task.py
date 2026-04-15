from datetime import datetime, timezone
from app import db

task_dependencies = db.Table('task_dependencies',
    db.Column('task_id', db.Integer, db.ForeignKey('tasks.id'), primary_key=True),
    db.Column('depends_on_id', db.Integer, db.ForeignKey('tasks.id'), primary_key=True)
)

class Task(db.Model):
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='todo') # 'todo', 'in_progress', 'done'
    is_completed = db.Column(db.Boolean, default=False)
    deadline = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime, nullable=True)
    approval_status = db.Column(db.String(20), nullable=True) # None, 'pending', 'approved', 'changes_requested'
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    approval_note = db.Column(db.Text, nullable=True)
    reminder_sent = db.Column(db.Boolean, default=False)
    
    # Relationships
    group = db.relationship('Group', back_populates='tasks')
    assignee = db.relationship('User', foreign_keys=[assigned_to], back_populates='tasks_assigned')
    creator = db.relationship('User', foreign_keys=[created_by], back_populates='tasks_created')
    approver = db.relationship('User', foreign_keys=[approved_by])
    time_logs = db.relationship('TimeLog', back_populates='task', cascade='all, delete-orphan')
    estimate = db.relationship('TaskEstimate', back_populates='task', uselist=False, cascade='all, delete-orphan')
    
    dependencies = db.relationship(
        'Task', 
        secondary=task_dependencies,
        primaryjoin=id==task_dependencies.c.task_id,
        secondaryjoin=id==task_dependencies.c.depends_on_id,
        backref='dependent_tasks'
    )

    @property
    def total_time_logged(self):
        return sum(log.duration_minutes for log in self.time_logs) if self.time_logs else 0

    @property
    def total_time_formatted(self):
        from app.utils.time_tracking import minutes_to_formatted
        return minutes_to_formatted(self.total_time_logged)

    @property
    def estimated_minutes(self):
        return self.estimate.estimated_minutes if self.estimate else None

    @property
    def time_variance_minutes(self):
        if self.estimated_minutes is None:
            return None
        return self.estimated_minutes - self.total_time_logged

    @property
    def deadline_status(self):
        if self.is_completed or not self.deadline:
            return "ok"
        now_dt = datetime.now(timezone.utc)
        dl_date = self.deadline.date() if isinstance(self.deadline, datetime) else self.deadline
        days_remaining = (dl_date - now_dt.date()).days
        if days_remaining < 0:
            return "overdue"
        elif days_remaining <= 2:
            return "critical"
        elif days_remaining <= 5:
            return "warning"
        return "ok"

    def to_dict(self):
        return {
            'id': self.id,
            'group_id': self.group_id,
            'title': self.title,
            'description': self.description,
            'assigned_to': self.assigned_to,
            'created_by': self.created_by,
            'status': self.status,
            'is_completed': self.is_completed,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'deadline_status': self.deadline_status,
            'reminder_sent': self.reminder_sent,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'approval_status': self.approval_status,
            'approved_by': self.approved_by,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'approval_note': self.approval_note
        }
