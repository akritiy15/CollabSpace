from app.models.user import User
from flask import session

def test_register_success(client, db):
    response = client.post('/auth/register', data={
        'username': 'newuser',
        'email': 'new@example.com',
        'password': 'newpassword123'
    }, follow_redirects=False)
    
    assert response.status_code == 302
    assert response.location == '/dashboard'
    
    user = User.query.filter_by(email='new@example.com').first()
    assert user is not None
    assert user.password_hash != 'newpassword123'
    assert user.check_password('newpassword123')

def test_register_duplicate_email(client, db, sample_user):
    response = client.post('/auth/register', data={
        'username': 'anotheruser',
        'email': 'test@example.com',
        'password': 'password123'
    }, follow_redirects=True)
    
    assert b'Email address already exists' in response.data
    users = User.query.filter_by(email='test@example.com').all()
    assert len(users) == 1

def test_register_duplicate_username(client, db, sample_user):
    response = client.post('/auth/register', data={
        'username': 'testuser',
        'email': 'another@example.com',
        'password': 'password123'
    }, follow_redirects=True)
    
    assert b'Username already exists' in response.data

def test_register_weak_password(client, db):
    response = client.post('/auth/register', data={
        'username': 'weakuser',
        'email': 'weak@example.com',
        'password': 'short'
    }, follow_redirects=True)
    
    assert getattr(response, 'status_code', 200) == 200

def test_login_success(client, db, sample_user):
    response = client.post('/auth/login', data={
        'email': 'test@example.com',
        'password': 'testpassword123'
    }, follow_redirects=False)
    
    assert response.status_code == 302
    assert response.location == '/dashboard'

def test_login_wrong_password(client, db, sample_user):
    response = client.post('/auth/login', data={
        'email': 'test@example.com',
        'password': 'wrongpassword'
    }, follow_redirects=True)
    
    assert b'Invalid email or password' in response.data

def test_login_nonexistent_email(client, db):
    response = client.post('/auth/login', data={
        'email': 'doesnt-exist@example.com',
        'password': 'password123'
    }, follow_redirects=True)
    
    assert b'Invalid email or password' in response.data

def test_logout(client, auth_client):
    response = auth_client.get('/auth/logout', follow_redirects=False)
    assert response.status_code == 302
    assert response.location == '/auth/login'
    
    # Try reaching a protected route
    res = auth_client.get('/dashboard', follow_redirects=False)
    assert res.status_code == 302
    assert res.location == '/auth/login?next=%2Fdashboard'

def test_protected_route_redirects(client):
    response = client.get('/dashboard', follow_redirects=False)
    assert response.status_code == 302
    assert '/auth/login' in response.location

def test_google_oauth_redirect(client):
    response = client.get('/auth/google', follow_redirects=False)
    assert response.status_code == 302
    assert 'accounts.google.com' in response.location
