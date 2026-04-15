from app import db

class UserNotificationPrefs(db.Model):
    __tablename__ = 'user_notification_prefs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    task_assignment_emails = db.Column(db.Boolean, default=True)
    deadline_reminder_emails = db.Column(db.Boolean, default=True)
    weekly_summary_emails = db.Column(db.Boolean, default=True)
    member_joined_emails = db.Column(db.Boolean, default=True)

    user = db.relationship('User', backref=db.backref('notification_prefs', uselist=False))

from datetime import datetime, timezone

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    link = db.Column(db.String(500), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref=db.backref('notifications', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'message': self.message,
            'link': self.link,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
