from datetime import datetime, timezone
from app import db

# Action types
TASK_CREATED = 'TASK_CREATED'
TASK_COMPLETED = 'TASK_COMPLETED'
TASK_DELETED = 'TASK_DELETED'
TASK_ASSIGNED = 'TASK_ASSIGNED'
MEMBER_JOINED = 'MEMBER_JOINED'
MEMBER_LEFT = 'MEMBER_LEFT'
REPORT_GENERATED = 'REPORT_GENERATED'
ROLE_CHANGED = 'ROLE_CHANGED'
TIME_LOGGED = 'TIME_LOGGED'

class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    meta_data = db.Column('metadata', db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    group = db.relationship('Group', back_populates='activities')
    user = db.relationship('User', back_populates='activities')

    def get_relative_timestamp(self):
        if not self.created_at:
            return ""
            
        now = datetime.now(timezone.utc)
        created_at = self.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
            
        diff = now - created_at
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 2592000:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        else:
            months = int(seconds / 2592000)
            return f"{months} month{'s' if months != 1 else ''} ago"

    def to_dict(self):
        return {
            'id': self.id,
            'group_id': self.group_id,
            'user_id': self.user_id,
            'action_type': self.action_type,
            'description': self.description,
            'metadata': self.meta_data,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'relative_timestamp': self.get_relative_timestamp()
        }
