from datetime import datetime, timezone
import json
from app import db

class MeetingNote(db.Model):
    __tablename__ = 'meeting_notes'
    
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    raw_notes = db.Column(db.Text)
    summary = db.Column(db.Text)
    key_decisions = db.Column(db.Text) # JSON string of decisions list
    tasks_extracted = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    group = db.relationship('Group', back_populates='meeting_notes')
    creator = db.relationship('User', foreign_keys=[created_by])

    def to_dict(self):
        try:
            key_decisions_list = json.loads(self.key_decisions) if self.key_decisions else []
        except:
            key_decisions_list = []
            
        return {
            'id': self.id,
            'group_id': self.group_id,
            'created_by': self.created_by,
            'title': self.title,
            'raw_notes': self.raw_notes,
            'summary': self.summary,
            'key_decisions': self.key_decisions,
            'tasks_extracted': self.tasks_extracted,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by_username': self.creator.username if self.creator else None,
            'created_by_avatar': self.creator.profile_picture if self.creator and getattr(self.creator, 'profile_picture', None) else None,
            'created_at_formatted': self.created_at.strftime("%d %b %Y, %I:%M %p") if self.created_at else None,
            'key_decisions_list': key_decisions_list
        }
