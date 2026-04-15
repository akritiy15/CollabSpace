from app.models.group import Group, GroupMember
from app.models.user import User

def test_create_group(auth_client, sample_user, db):
    response = auth_client.post('/groups/create', data={
        'name': 'My New Group',
        'description': 'Description here'
    }, follow_redirects=False)
    
    assert response.status_code == 302
    
    group = Group.query.filter_by(name='My New Group').first()
    assert group is not None
    assert group.created_by == sample_user.id
    assert len(group.invite_code) == 8
    
    member = GroupMember.query.filter_by(group_id=group.id, user_id=sample_user.id).first()
    assert member.role == 'admin'

def test_create_group_no_name(auth_client, db):
    response = auth_client.post('/groups/create', data={
        'name': '',
        'description': 'No name'
    }, follow_redirects=True)
    
    assert b'Group name is required' in response.data
    group = Group.query.filter_by(description='No name').first()
    assert group is None

def test_join_group_valid_code(auth_client, sample_user, sample_group, db):
    response = auth_client.post('/groups/join', data={
        'invite_code': sample_group.invite_code
    }, follow_redirects=False)
    
    assert response.status_code == 302
    assert response.location == f'/groups/{sample_group.id}'
    
    member = GroupMember.query.filter_by(group_id=sample_group.id, user_id=sample_user.id).first()
    assert member is not None
    assert member.role == 'editor'

def test_join_group_invalid_code(auth_client, db):
    response = auth_client.post('/groups/join', data={
        'invite_code': 'FAKECODE'
    }, follow_redirects=True)
    
    assert b'Invalid invite code' in response.data

def test_join_group_already_member(admin_client, sample_group, db):
    response = admin_client.post('/groups/join', data={
        'invite_code': sample_group.invite_code
    }, follow_redirects=True)
    
    assert b'You are already a member' in response.data

def test_group_dashboard_member_only(auth_client, sample_group):
    # auth_client (sample_user) is not in sample_group (created by sample_admin)
    response = auth_client.get(f'/groups/{sample_group.id}')
    assert response.status_code == 403

def test_change_member_role(admin_client, sample_admin, sample_user, sample_group, db):
    # Add sample_user to group
    member = GroupMember(group_id=sample_group.id, user_id=sample_user.id, role='editor')
    db.session.add(member)
    db.session.commit()
    
    response = admin_client.post(f'/groups/{sample_group.id}/change-role/{sample_user.id}', json={
        'new_role': 'viewer'
    })
    assert response.status_code == 200
    
    updated_member = GroupMember.query.filter_by(group_id=sample_group.id, user_id=sample_user.id).first()
    assert updated_member.role == 'viewer'

def test_change_role_non_admin(auth_client, sample_user, sample_admin, sample_group, db):
    # Auth client is an editor
    member = GroupMember(group_id=sample_group.id, user_id=sample_user.id, role='editor')
    db.session.add(member)
    db.session.commit()
    
    response = auth_client.post(f'/groups/{sample_group.id}/change-role/{sample_admin.id}', json={
        'new_role': 'viewer'
    })
    assert response.status_code == 403

def test_leave_group(auth_client, sample_user, sample_group, db):
    member = GroupMember(group_id=sample_group.id, user_id=sample_user.id, role='editor')
    db.session.add(member)
    db.session.commit()
    
    response = auth_client.post(f'/groups/{sample_group.id}/leave', follow_redirects=False)
    assert response.status_code == 302
    assert response.location == '/dashboard'
    
    member_check = GroupMember.query.filter_by(group_id=sample_group.id, user_id=sample_user.id).first()
    assert member_check is None

def test_only_admin_cannot_leave(admin_client, sample_group):
    response = admin_client.post(f'/groups/{sample_group.id}/leave', follow_redirects=True)
    assert b'You are the only admin' in response.data

def test_regenerate_invite_code(admin_client, sample_group, db):
    old_code = sample_group.invite_code
    response = admin_client.post(f'/groups/{sample_group.id}/regenerate-invite')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['new_code'] != old_code
    
    group = Group.query.get(sample_group.id)
    assert group.invite_code != old_code
