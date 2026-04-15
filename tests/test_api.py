from app.models.group import Group
from app.models.task import Task

def test_api_login_success(client, sample_user):
    response = client.post('/api/v1/auth/login', json={
        'email': 'test@example.com',
        'password': 'testpassword123'
    })
    assert response.status_code == 200
    data = response.get_json()['data']
    assert 'access_token' in data
    assert 'refresh_token' in data
    assert data['user']['email'] == 'test@example.com'

def test_api_login_wrong_password(client, sample_user):
    response = client.post('/api/v1/auth/login', json={
        'email': 'test@example.com',
        'password': 'wrongpassword'
    })
    assert response.status_code == 401
    assert response.get_json()['error'] is not None

def test_api_me(client, api_headers):
    response = client.get('/api/v1/auth/me', headers=api_headers)
    assert response.status_code == 200
    assert response.get_json()['data']['email'] == 'test@example.com'

def test_api_me_no_token(client):
    response = client.get('/api/v1/auth/me')
    assert response.status_code == 401
    assert response.get_json()['success'] is False

def test_api_get_groups(client, admin_api_headers, sample_group):
    response = client.get('/api/v1/groups/', headers=admin_api_headers)
    assert response.status_code == 200
    data = response.get_json()['data']
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]['name'] == 'Test Group'
    assert 'member_count' in data[0]

def test_api_create_group(client, admin_api_headers, db):
    response = client.post('/api/v1/groups/', headers=admin_api_headers, json={
        'name': 'API Group',
        'description': 'Created via API'
    })
    assert response.status_code == 201
    group_id = response.get_json()['data']['id']
    group = Group.query.get(group_id)
    assert group is not None
    assert group.name == 'API Group'

def test_api_get_tasks(client, admin_api_headers, sample_group, db):
    task = Task(title='API Task', group_id=sample_group.id, created_by=sample_group.created_by)
    db.session.add(task)
    db.session.commit()
    
    response = client.get(f'/api/v1/groups/{sample_group.id}/tasks/', headers=admin_api_headers)
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['success'] is True
    assert json_data['error'] is None
    assert len(json_data['data']) == 1
    assert json_data['data'][0]['title'] == 'API Task'

def test_api_create_task(client, admin_api_headers, sample_group):
    response = client.post(f'/api/v1/groups/{sample_group.id}/tasks/', headers=admin_api_headers, json={
        'title': 'New API Task',
        'description': 'Desc'
    })
    assert response.status_code == 201
    task_id = response.get_json()['data']['id']
    assert Task.query.get(task_id) is not None

def test_api_update_task(client, admin_api_headers, sample_group, db):
    task = Task(title='To Update', group_id=sample_group.id, created_by=sample_group.created_by)
    db.session.add(task)
    db.session.commit()
    
    response = client.patch(f'/api/v1/groups/{sample_group.id}/tasks/{task.id}/', headers=admin_api_headers, json={
        'status': 'done'
    })
    assert response.status_code == 200
    assert Task.query.get(task.id).status == 'done'

def test_api_delete_task_as_admin(client, admin_api_headers, sample_group, db):
    task = Task(title='To Delete', group_id=sample_group.id, created_by=sample_group.created_by)
    db.session.add(task)
    db.session.commit()
    
    response = client.delete(f'/api/v1/groups/{sample_group.id}/tasks/{task.id}/', headers=admin_api_headers)
    assert response.status_code == 200
    assert Task.query.get(task.id) is None

def test_api_delete_task_as_editor(client, api_headers, sample_user, sample_group, db):
    from app.models.group import GroupMember
    member = GroupMember(group_id=sample_group.id, user_id=sample_user.id, role='editor')
    task = Task(title='Editor Delete', group_id=sample_group.id, created_by=sample_group.created_by)
    db.session.add_all([member, task])
    db.session.commit()
    
    response = client.delete(f'/api/v1/groups/{sample_group.id}/tasks/{task.id}/', headers=api_headers)
    assert response.status_code == 403

def test_api_non_member_access(client, api_headers, sample_user, sample_group):
    # sample_user is not a member of sample_group
    response = client.get(f'/api/v1/groups/{sample_group.id}/tasks/', headers=api_headers)
    assert response.status_code == 403

def test_api_invalid_token(client):
    response = client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer fake_token'})
    assert response.status_code == 401

def test_api_report_as_admin(client, admin_api_headers, sample_group):
    response = client.get(f'/api/v1/groups/{sample_group.id}/report/', headers=admin_api_headers)
    assert response.status_code == 200
    data = response.get_json()['data']
    assert 'summary' in data
    assert 'tasks' in data
    assert 'members' in data
def test_api_report_as_editor(client, api_headers, sample_user, sample_group, db):
    from app.models.group import GroupMember
    member = GroupMember(group_id=sample_group.id, user_id=sample_user.id, role='editor')
    db.session.add(member)
    db.session.commit()
    
    response = client.get(f'/api/v1/groups/{sample_group.id}/report/', headers=api_headers)
    assert response.status_code == 403
