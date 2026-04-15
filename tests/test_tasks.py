from app.models.task import Task
from app.models.group import GroupMember

def test_create_task_as_editor(admin_client, sample_group, sample_admin, db):
    # admin serves as an editor-role capable user
    response = admin_client.post(f'/groups/{sample_group.id}/tasks/create', json={
        'title': 'New Task',
        'description': 'Task Description'
    })
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    
    task = Task.query.first()
    assert task is not None
    assert task.status == 'todo'
    assert task.title == 'New Task'

def test_create_task_as_viewer(auth_client, sample_user, sample_group, db):
    member = GroupMember(group_id=sample_group.id, user_id=sample_user.id, role='viewer')
    db.session.add(member)
    db.session.commit()
    
    response = auth_client.post(f'/groups/{sample_group.id}/tasks/create', json={
        'title': 'New Task'
    })
    
    assert response.status_code == 403

def test_create_task_no_title(admin_client, sample_group):
    response = admin_client.post(f'/groups/{sample_group.id}/tasks/create', json={
        'description': 'No title here'
    })
    
    data = response.get_json()
    assert data['success'] is False
    assert 'Title is required' in data['message']

def test_complete_task(admin_client, sample_group, sample_admin, db):
    task = Task(title='Test Task', group_id=sample_group.id, status='todo', created_by=sample_group.created_by)
    db.session.add(task)
    db.session.commit()
    
    response = admin_client.patch(f'/groups/{sample_group.id}/tasks/{task.id}', json={
        'status': 'done'
    })
    
    assert response.status_code == 200
    updated_task = Task.query.get(task.id)
    assert updated_task.is_completed is True
    assert updated_task.completed_at is not None
    assert updated_task.status == 'done'

def test_uncomplete_task(admin_client, sample_group, db):
    task = Task(title='Test Task', group_id=sample_group.id, status='done', is_completed=True, created_by=sample_group.created_by)
    db.session.add(task)
    db.session.commit()
    
    response = admin_client.patch(f'/groups/{sample_group.id}/tasks/{task.id}', json={
        'status': 'todo'
    })
    
    updated_task = Task.query.get(task.id)
    assert updated_task.is_completed is False
    assert updated_task.completed_at is None

def test_assign_task(admin_client, sample_user, sample_group, db):
    member = GroupMember(group_id=sample_group.id, user_id=sample_user.id, role='editor')
    db.session.add(member)
    task = Task(title='Assign Me', group_id=sample_group.id, created_by=sample_group.created_by)
    db.session.add(task)
    db.session.commit()
    
    response = admin_client.patch(f'/groups/{sample_group.id}/tasks/{task.id}', json={
        'assigned_to': sample_user.id
    })
    
    updated_task = Task.query.get(task.id)
    assert updated_task.assigned_to == sample_user.id

def test_assign_to_non_member(admin_client, sample_user, sample_group, db):
    # sample_user is NOT added to sample_group
    task = Task(title='Assign Me', group_id=sample_group.id, created_by=sample_group.created_by)
    db.session.add(task)
    db.session.commit()
    
    # Passing through the web route format: The frontend usually drops a None if not found or errors if the logic expects one
    response = admin_client.patch(f'/groups/{sample_group.id}/tasks/{task.id}', json={
        'assigned_to': sample_user.id
    })
    
    updated_task = Task.query.get(task.id)
    # the code states if not member, it ignores assignment or doesn't assign
    assert updated_task.assigned_to is None

def test_delete_task_as_admin(admin_client, sample_group, db):
    task = Task(title='Delete Me', group_id=sample_group.id, created_by=sample_group.created_by)
    db.session.add(task)
    db.session.commit()
    
    response = admin_client.delete(f'/groups/{sample_group.id}/tasks/{task.id}')
    assert response.status_code == 200
    
    assert Task.query.get(task.id) is None

def test_delete_task_as_editor(auth_client, sample_user, sample_group, db):
    member = GroupMember(group_id=sample_group.id, user_id=sample_user.id, role='editor')
    task = Task(title='Try Delete', group_id=sample_group.id, created_by=sample_group.created_by)
    db.session.add_all([member, task])
    db.session.commit()
    
    response = auth_client.delete(f'/groups/{sample_group.id}/tasks/{task.id}')
    assert response.status_code == 403

def test_task_filter_by_status(auth_client, sample_user, sample_group, db):
    member = GroupMember(group_id=sample_group.id, user_id=sample_user.id, role='editor')
    task1 = Task(title='T1', group_id=sample_group.id, status='todo', created_by=sample_group.created_by)
    task2 = Task(title='T2', group_id=sample_group.id, status='done', is_completed=True, created_by=sample_group.created_by)
    db.session.add_all([member, task1, task2])
    db.session.commit()
    
    response = auth_client.get(f'/groups/{sample_group.id}/tasks/?status=todo')
    assert b'T1' in response.data
    # Testing html response includes specific filters

def test_task_filter_my_tasks(auth_client, sample_user, sample_group, db):
    member = GroupMember(group_id=sample_group.id, user_id=sample_user.id, role='editor')
    task1 = Task(title='My Task', group_id=sample_group.id, assigned_to=sample_user.id, created_by=sample_group.created_by)
    task2 = Task(title='Other Task', group_id=sample_group.id, created_by=sample_group.created_by)
    db.session.add_all([member, task1, task2])
    db.session.commit()
    
    response = auth_client.get(f'/groups/{sample_group.id}/tasks/?assigned=me')
    # Because it renders HTML, it will populate `tasks` with only task1. We can assert the string 'My Task' is in response
    assert b'My Task' in response.data
    assert b'Other Task' not in response.data

def test_kanban_status_update(admin_client, sample_group, db):
    task = Task(title='Drag Me', group_id=sample_group.id, status='todo', created_by=sample_group.created_by)
    db.session.add(task)
    db.session.commit()
    
    response = admin_client.patch(f'/groups/{sample_group.id}/tasks/{task.id}', json={
        'status': 'in_progress'
    })
    
    updated_task = Task.query.get(task.id)
    assert updated_task.status == 'in_progress'
    assert updated_task.is_completed is False
