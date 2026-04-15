from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    bio = db.Column(db.String(255))
    profile_picture = db.Column(db.String(255))
    is_google_user = db.Column(db.Boolean, default=False)
    account_type = db.Column(db.String(20), default='student')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    groups_created = db.relationship('Group', back_populates='creator', lazy='dynamic')
    group_memberships = db.relationship('GroupMember', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    tasks_assigned = db.relationship('Task', foreign_keys='Task.assigned_to', back_populates='assignee', lazy='dynamic')
    tasks_created = db.relationship('Task', foreign_keys='Task.created_by', back_populates='creator', lazy='dynamic')
    sent_requests = db.relationship('MemberConnection', foreign_keys='MemberConnection.sender_id', back_populates='sender', lazy='dynamic', cascade='all, delete-orphan')
    received_requests = db.relationship('MemberConnection', foreign_keys='MemberConnection.receiver_id', back_populates='receiver', lazy='dynamic', cascade='all, delete-orphan')

    activities = db.relationship('ActivityLog', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    mentor_profile = db.relationship('MentorProfile', back_populates='user', uselist=False, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
        
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'bio': self.bio,
            'profile_picture': self.profile_picture,
            'is_google_user': self.is_google_user,
            'account_type': self.account_type,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
