from flask import Blueprint, render_template, request, flash, redirect, url_for, send_file, abort
from flask_login import login_required, current_user
from app import db
from app.models.group import Group, GroupMember
from app.models.task import Task
from app.models.activity import ActivityLog
from app.models.report import ReportLog
from app.utils.report import generate_pdf_report
from app.utils.activity import log_activity
from datetime import datetime, timedelta, timezone
from functools import wraps
from app.utils.decorators import require_account_type

reports_bp = Blueprint('reports', __name__, url_prefix='/groups/<int:group_id>/report')

def require_admin(f):
    @wraps(f)
    def decorated_function(group_id, *args, **kwargs):
        if current_user.is_authenticated:
            member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
            if not member or member.role != 'admin':
                abort(403)
        return f(group_id, *args, **kwargs)
    return decorated_function

def get_report_data(group_id):
    group = Group.query.get_or_404(group_id)
    from app.utils.report import calculate_report_data
    report_data = calculate_report_data(group)
    report_data['generated_by'] = current_user
    report_data['generated_at'] = datetime.now(timezone.utc)
    return report_data

@reports_bp.route('/preview')
@login_required
@require_admin
@require_account_type('mentor', 'team_leader')
def preview(group_id):
    data = get_report_data(group_id)
    return render_template('reports/preview.html', **data)

@reports_bp.route('/download')
@login_required
@require_admin
@require_account_type('mentor', 'team_leader')
def download(group_id):
    data = get_report_data(group_id)
    
    # Generate the PDF Buffer
    pdf_buffer = generate_pdf_report(data)
    
    # Log it
    fn = f"{data['group_name'].replace(' ', '_')}_report_{datetime.now().strftime('%Y%m%d')}.pdf"
    rl = ReportLog(
        group_id=group_id,
        generated_by=current_user.id,
        filename=fn,
        task_count=data['overall']['total_tasks'],
        member_count=data['overall']['total_members']
    )
    db.session.add(rl)
    db.session.commit()
    
    log_activity(group_id, current_user.id, 'REPORT_GENERATED', f"Generated {fn}")
    
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=fn,
        mimetype='application/pdf'
    )

@reports_bp.route('/history')
@login_required
@require_admin
@require_account_type('mentor', 'team_leader')
def history(group_id):
    group = Group.query.get_or_404(group_id)
    logs = ReportLog.query.filter_by(group_id=group_id).order_by(ReportLog.generated_at.desc()).all()
    return render_template('reports/history.html', group=group, reports=logs)
