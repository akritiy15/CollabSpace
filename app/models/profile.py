from app import db
from datetime import datetime, timezone

class StudentAcademicProfile(db.Model):
    __tablename__ = 'student_academic_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    
    semester = db.Column(db.Integer, nullable=True)
    branch = db.Column(db.String(100), nullable=True)
    institution = db.Column(db.String(200), nullable=True)
    enrollment_number = db.Column(db.String(100), nullable=True)
    admission_year = db.Column(db.Integer, nullable=True)
    
    linkedin_url = db.Column(db.String(300), nullable=True)
    github_url = db.Column(db.String(300), nullable=True)
    
    skills = db.Column(db.JSON, nullable=True, default=list) # List of skills
    availability_hours_per_week = db.Column(db.Integer, nullable=True)
    
    # Track when the profile was last updated
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user = db.relationship('User', backref=db.backref('academic_profile', uselist=False))
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'semester': self.semester,
            'branch': self.branch,
            'institution': self.institution,
            'enrollment_number': self.enrollment_number,
            'admission_year': self.admission_year,
            'linkedin_url': self.linkedin_url,
            'github_url': self.github_url,
            'skills': self.skills,
            'availability_hours_per_week': self.availability_hours_per_week
        }
