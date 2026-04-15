from app import db
from datetime import datetime, timezone

class StudentScore(db.Model):
    __tablename__ = 'student_scores'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    sprint_label = db.Column(db.String(50), nullable=True)
    
    tasks_score = db.Column(db.Float, default=0.0)
    hours_score = db.Column(db.Float, default=0.0)
    peer_score = db.Column(db.Float, default=0.0)
    mentor_rating = db.Column(db.Float, default=0.0)
    final_score = db.Column(db.Float, default=0.0)
    
    calculated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    student = db.relationship('User', foreign_keys=[student_id], backref=db.backref('scores', lazy='dynamic'))
    group = db.relationship('Group', backref=db.backref('student_scores', lazy='dynamic'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'group_id': self.group_id,
            'sprint_label': self.sprint_label,
            'tasks_score': self.tasks_score,
            'hours_score': self.hours_score,
            'peer_score': self.peer_score,
            'mentor_rating': self.mentor_rating,
            'final_score': self.final_score,
            'calculated_at': self.calculated_at.isoformat() if self.calculated_at else None
        }
