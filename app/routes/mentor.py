from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.mentor import MentorProfile
from app.models.group import Group, GroupMember
from app.utils.mentor import get_mentor_overview, get_group_student_detail
from app.utils.report import calculate_report_data, generate_pdf_report
from datetime import datetime, timezone

mentor_bp = Blueprint('mentor', __name__, url_prefix='/mentor')

@mentor_bp.route('/dashboard')
@login_required
def dashboard():
    overview = get_mentor_overview(current_user.id)
    return render_template('mentor/dashboard.html', 
                           overview=overview, 
                           current_user=current_user)

@mentor_bp.route('/setup', methods=['GET', 'POST'])
@login_required
def setup():
    if request.method == 'POST':
        department = request.form.get('department')
        designation = request.form.get('designation')
        max_students = request.form.get('max_students', 10, type=int)
        
        if not current_user.mentor_profile:
            profile = MentorProfile(user=current_user)
            db.session.add(profile)
        else:
            profile = current_user.mentor_profile
            
        profile.department = department
        profile.designation = designation
        profile.max_students = max_students
        
        db.session.commit()
        flash('Mentor profile updated successfully!', 'success')
        return redirect(url_for('mentor.dashboard'))
        
    return render_template('mentor/setup.html', current_user=current_user)

@mentor_bp.route('/groups/<int:group_id>')
@login_required
def group_detail(group_id):
    detail = get_group_student_detail(group_id, current_user.id)
    if not detail:
        flash('You do not have access to this group.', 'danger')
        return redirect(url_for('mentor.dashboard'))
        
    return render_template('mentor/group_detail.html', detail=detail)

@mentor_bp.route('/groups/<int:group_id>/report')
@login_required
def group_report(group_id):
    membership = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id, role='admin').first()
    if not membership:
        flash('You do not have access to this group report.', 'danger')
        return redirect(url_for('mentor.dashboard'))
        
    group = membership.group
    
    # Reuse report logic
    data = calculate_report_data(group)
    data['generated_by'] = current_user
    pdf_buffer = generate_pdf_report(data)
    
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=f"Project_Report_{group.name}.pdf",
        mimetype='application/pdf'
    )

@mentor_bp.route('/groups/create-student-group', methods=['POST'])
@login_required
def create_student_group():
    data = request.json
    project_name = data.get('project_name')
    description = data.get('description', '')
    student_emails = data.get('student_emails', [])
    
    if not project_name:
        return jsonify({'success': False, 'error': 'Project name is required'}), 400
        
    group = Group(name=project_name, description=description, created_by=current_user.id)
    db.session.add(group)
    db.session.flush() # Get group ID
    
    admin_member = GroupMember(group_id=group.id, user_id=current_user.id, role='admin')
    db.session.add(admin_member)
    
    students_added = 0
    students_not_found = []
    
    for email in student_emails:
        email = email.strip()
        if not email:
            continue
        user = User.query.filter_by(email=email).first()
        if user:
            member = GroupMember(group_id=group.id, user_id=user.id, role='editor')
            db.session.add(member)
            students_added += 1
        else:
            students_not_found.append(email)
            
    db.session.commit()
    
    return jsonify({
        'success': True,
        'group_id': group.id,
        'invite_code': group.invite_code,
        'students_added': students_added,
        'students_not_found': students_not_found
    })

@mentor_bp.route('/dashboard/stats')
@login_required
def dashboard_stats():
    overview = get_mentor_overview(current_user.id)
    # Lightweight JSON update
    stats = []
    for g in overview['groups']:
        stats.append({
            'group_id': g['id'],
            'health_score': g['health_score'],
            'health_status': g['health_status'],
            'health_color': g['health_color'],
            'completed_tasks': g['completed_tasks'],
            'total_tasks': g['total_tasks'],
            'last_activity_relative': g['last_activity_relative'],
            'overdue_count': g['overdue_tasks']
        })
    return jsonify({'success': True, 'stats': stats})
