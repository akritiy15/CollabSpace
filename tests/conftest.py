import pytest
from app import create_app, db as _db
from app.models.user import User
from app.models.group import Group, GroupMember
from unittest.mock import patch

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    app = create_app('testing')
    
    with app.app_context():
        yield app

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def db(app):
    """Database fixture for each test."""
    _db.create_all()
    yield _db
    _db.session.remove()
    _db.drop_all()

@pytest.fixture
def sample_user(db):
    user = User(username='testuser', email='test@example.com')
    user.set_password('testpassword123')
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def sample_admin(db):
    admin = User(username='adminuser', email='admin@example.com')
    admin.set_password('adminpassword123')
    db.session.add(admin)
    db.session.commit()
    return admin

@pytest.fixture
def sample_group(db, sample_admin):
    group = Group(name='Test Group', description='A test group', created_by=sample_admin.id)
    group.invite_code = 'TEST1234'
    db.session.add(group)
    db.session.commit()
    
    member = GroupMember(group_id=group.id, user_id=sample_admin.id, role='admin')
    db.session.add(member)
    db.session.commit()
    
    return group

@pytest.fixture
def auth_client(client, sample_user):
    client.post('/auth/login', data=dict(
        email='test@example.com',
        password='testpassword123'
    ))
    return client

@pytest.fixture
def admin_client(client, sample_admin):
    client.post('/auth/login', data=dict(
        email='admin@example.com',
        password='adminpassword123'
    ))
    return client

@pytest.fixture
def api_headers(client, sample_user):
    response = client.post('/api/v1/auth/login', json={
        'email': 'test@example.com',
        'password': 'testpassword123'
    })
    token = response.get_json()['data']['access_token']
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

@pytest.fixture
def admin_api_headers(client, sample_admin):
    response = client.post('/api/v1/auth/login', json={
        'email': 'admin@example.com',
        'password': 'adminpassword123'
    })
    token = response.get_json()['data']['access_token']
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

# Mock out celery and sockets automatically across the test suite
@pytest.fixture(autouse=True)
def mock_external_calls():
    with patch('app.socketio.emit') as mock_emit, \
         patch('app.tasks.email_tasks.send_task_assignment_email.delay') as mock_email:
        yield mock_emit, mock_email
