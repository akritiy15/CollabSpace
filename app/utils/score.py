from app.models.score import StudentScore
from app.models.task import Task
from app.models.time_tracking import TimeLog
from app import db
from datetime import datetime, timezone

def calculate_student_score(student_id, group_id, sprint_label="Overall"):
    # Ensure a score record exists
    score = StudentScore.query.filter_by(
        student_id=student_id, 
        group_id=group_id, 
        sprint_label=sprint_label
    ).first()
    
    if not score:
        score = StudentScore(
            student_id=student_id,
            group_id=group_id,
            sprint_label=sprint_label,
            peer_score=100.0,
            mentor_rating=100.0
        )
        db.session.add(score)
        
    tasks = Task.query.filter_by(assigned_to=student_id, group_id=group_id).all()
    
    # 1. Tasks Score (max 100)
    if not tasks:
        score.tasks_score = 0.0
    else:
        assigned = len(tasks)
        score_val = 0
        for t in tasks:
            if t.is_completed:
                on_time = True
                if t.deadline and t.completed_at:
                    if t.completed_at.date() > t.deadline.date():
                        on_time = False
                if on_time:
                    score_val += 100
                else:
                    score_val += 70  # partial credit for late tasks
        score.tasks_score = score_val / assigned if assigned > 0 else 0.0

    # 2. Hours Score (max 100)
    total_estimated = sum(t.estimated_minutes for t in tasks if t.estimated_minutes)
    logs = TimeLog.query.filter_by(user_id=student_id, group_id=group_id).all()
    total_logged = sum((l.duration_minutes or 0) for l in logs)
    
    if not total_estimated:
        score.hours_score = 100.0 if total_logged > 0 else 0.0
    else:
        ratio = total_logged / total_estimated
        # If they log at least 80% of estimated, full score.
        if ratio >= 0.8:
            score.hours_score = 100.0
        else:
            score.hours_score = (ratio / 0.8) * 100.0
            
    # Default initial states for peer/mentor
    if score.peer_score is None: score.peer_score = 100.0
    if score.mentor_rating is None: score.mentor_rating = 100.0
    
    # Final Score weighted
    # Tasks 50%, Hours 30%, Peer 10%, Mentor 10%
    score.final_score = (
        (score.tasks_score * 0.5) +
        (score.hours_score * 0.3) +
        (score.peer_score * 0.1) +
        (score.mentor_rating * 0.1)
    )
    
    score.calculated_at = datetime.now(timezone.utc)
    
    db.session.commit()
    return score
