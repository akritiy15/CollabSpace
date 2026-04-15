from datetime import datetime, timezone
from app import db

class MentorProfile(db.Model):
    __tablename__ = 'mentor_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    department = db.Column(db.String(100), nullable=True)
    designation = db.Column(db.String(100), nullable=True)
    max_students = db.Column(db.Integer, default=10)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship
    user = db.relationship('User', back_populates='mentor_profile')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'department': self.department,
            'designation': self.designation,
            'max_students': self.max_students,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
