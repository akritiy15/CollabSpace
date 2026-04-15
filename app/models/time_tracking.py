from datetime import datetime, timezone
from app import db

class TimeLog(db.Model):
    __tablename__ = 'time_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=False)
    logged_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    timer_start = db.Column(db.DateTime, nullable=True)
    is_running = db.Column(db.Boolean, default=False)

    # Relationships
    task = db.relationship('Task', back_populates='time_logs')
    group = db.relationship('Group', backref='time_logs')
    user = db.relationship('User', foreign_keys='TimeLog.user_id')

    def to_dict(self):
        # Local import to prevent circular dependencies
        from app.utils.time_tracking import minutes_to_formatted
        
        return {
            'id': self.id,
            'task_id': self.task_id,
            'group_id': self.group_id,
            'user_id': self.user_id,
            'description': self.description,
            'duration_minutes': self.duration_minutes,
            'duration_formatted': minutes_to_formatted(self.duration_minutes),
            'logged_date': self.logged_date.isoformat() if self.logged_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'user': {
                'id': self.user.id,
                'username': self.user.username,
                'profile_picture': getattr(self.user, 'profile_picture', None)
            } if self.user else None,
            'task': {
                'id': self.task.id,
                'title': self.task.title
            } if self.task else None
        }

class TaskEstimate(db.Model):
    __tablename__ = 'task_estimates'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False, unique=True)
    estimated_minutes = db.Column(db.Integer, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    task = db.relationship('Task', back_populates='estimate')
    creator = db.relationship('User', foreign_keys='TaskEstimate.created_by')

    def to_dict(self):
        # Local import to prevent circular dependencies
        from app.utils.time_tracking import minutes_to_formatted
        
        return {
            'id': self.id,
            'task_id': self.task_id,
            'estimated_minutes': self.estimated_minutes,
            'estimated_formatted': minutes_to_formatted(self.estimated_minutes),
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
