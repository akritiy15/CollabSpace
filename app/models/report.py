from datetime import datetime, timezone
from app import db

class ReportLog(db.Model):
    __tablename__ = 'report_logs'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    generated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    generated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    filename = db.Column(db.String(255), nullable=False)
    task_count = db.Column(db.Integer, default=0)
    member_count = db.Column(db.Integer, default=0)

    # Relationships
    group = db.relationship('Group', backref='reports')
    generator = db.relationship('User')

    def to_dict(self):
        return {
            'id': self.id,
            'group_id': self.group_id,
            'generated_by': self.generated_by,
            'generated_at': self.generated_at.isoformat() if self.generated_at else None,
            'filename': self.filename,
            'task_count': self.task_count,
            'member_count': self.member_count
        }
