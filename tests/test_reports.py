from app.models.task import Task

def test_report_preview_as_admin(admin_client, sample_group):
    response = admin_client.get(f'/groups/{sample_group.id}/report/preview')
    assert response.status_code == 200
    assert sample_group.name.encode() in response.data

def test_report_preview_as_editor(auth_client, sample_user, sample_group, db):
    member = GroupMember(group_id=sample_group.id, user_id=sample_user.id, role='editor')
    db.session.add(member)
    db.session.commit()
    
    response = auth_client.get(f'/groups/{sample_group.id}/report/preview')
    assert response.status_code == 403

def test_report_download_as_admin(admin_client, sample_group):
    response = admin_client.get(f'/groups/{sample_group.id}/report/download')
    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'application/pdf'
    assert 'attachment' in response.headers.get('Content-Disposition', '')
    assert len(response.data) > 0

def test_report_contains_correct_data(client, admin_api_headers, sample_admin, sample_user, sample_group, db):
    # Setup test condition
    member = GroupMember(group_id=sample_group.id, user_id=sample_user.id, role='editor')
    db.session.add(member)
    
    # 3 tasks, 2 completed
    t1 = Task(group_id=sample_group.id, title='T1', is_completed=True, assigned_to=sample_user.id, created_by=sample_group.created_by)
    t2 = Task(group_id=sample_group.id, title='T2', is_completed=True, assigned_to=sample_admin.id, created_by=sample_group.created_by)
    t3 = Task(group_id=sample_group.id, title='T3', is_completed=False, assigned_to=sample_user.id, created_by=sample_group.created_by)
    db.session.add_all([t1, t2, t3])
    
    assert summary['completed_tasks'] == 2
    assert summary['completion_rate'] == 67  # 66.66% rounded is usually 67. If logic is round(), 67 or 66.

def test_report_log_created(admin_client, sample_admin, sample_group, db):
    admin_client.get(f'/groups/{sample_group.id}/report/download')
    
    log = ReportLog.query.filter_by(group_id=sample_group.id).first()
    assert log is not None
    assert log.generated_by == sample_admin.id

def test_report_empty_group(admin_client, sample_group):
    response = admin_client.get(f'/groups/{sample_group.id}/report/download')
    assert response.status_code == 200
    # No exception generated
    # Valid PDF returned (simplest PDF has a few bytes)
    assert len(response.data) > 100
