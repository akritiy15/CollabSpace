import uuid
import string
import random
from datetime import datetime, timezone
from sqlalchemy import event
from app import db

class Group(db.Model):
    __tablename__ = 'groups'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    invite_code = db.Column(db.String(20), unique=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    creator = db.relationship('User', back_populates='groups_created')
    members = db.relationship('GroupMember', back_populates='group', lazy='dynamic', cascade='all, delete-orphan')
    tasks = db.relationship('Task', back_populates='group', lazy='dynamic', cascade='all, delete-orphan')
    activities = db.relationship('ActivityLog', back_populates='group', lazy='dynamic', cascade='all, delete-orphan')
    meeting_notes = db.relationship('MeetingNote', back_populates='group', lazy='dynamic', cascade='all, delete-orphan')

    def __init__(self, **kwargs):
        super(Group, self).__init__(**kwargs)
        if not self.invite_code:
            self.invite_code = self.generate_invite_code()
            
    @staticmethod
    def generate_invite_code(length=8):
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choice(chars) for _ in range(length))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'invite_code': self.invite_code,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class GroupMember(db.Model):
    __tablename__ = 'group_members'
    
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(20), default='editor') # 'admin', 'editor', 'viewer'
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    group = db.relationship('Group', back_populates='members')
    user = db.relationship('User', back_populates='group_memberships')

    def to_dict(self):
        return {
            'id': self.id,
            'group_id': self.group_id,
            'user_id': self.user_id,
            'role': self.role,
            'joined_at': self.joined_at.isoformat() if self.joined_at else None
        }

@event.listens_for(Group, 'after_insert')
def auto_create_group_admin(mapper, connection, target):
    connection.execute(
        GroupMember.__table__.insert().values(
            group_id=target.id,
            user_id=target.created_by,
            role='admin',
            joined_at=datetime.now(timezone.utc)
        )
    )
