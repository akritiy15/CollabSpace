from flask import Blueprint, request, redirect, url_for, flash, render_template, session
from flask_login import login_user, logout_user, login_required, current_user
from flask_dance.contrib.google import google
from oauthlib.oauth2.rfc6749.errors import TokenExpiredError
from werkzeug.security import generate_password_hash

from app import db
from app.models.user import User

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('auth/register.html')

    data = request.form if request.form else request.json
    if not data:
        flash("No input data provided", "error")
        return redirect(url_for('auth.login'))

    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    account_type = data.get('account_type', 'student')
    
    if account_type not in ['student', 'mentor', 'team_leader']:
        account_type = 'student'

    if not username or not email or not password:
        flash("Username, email, and password are required.", "error")
        return redirect(url_for('auth.register'))
    
    if len(password) < 8:
        flash("Password must be at least 8 characters long.", "error")
        return redirect(url_for('auth.register'))

    if User.query.filter_by(email=email).first():
        flash("Email is already taken.", "error")
        return redirect(url_for('auth.register'))
        
    if User.query.filter_by(username=username).first():
        flash("Username is already taken.", "error")
        return redirect(url_for('auth.register'))

    new_user = User(
        username=username,
        email=email,
        account_type=account_type
    )
    new_user.set_password(password)

    db.session.add(new_user)
    db.session.commit()

    login_user(new_user)
    flash("Registration successful!", "success")
    return redirect('/dashboard')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        # Clear the google oauth token forcing a fresh login prompt at Google
        session.pop('google_oauth_token', None)
        return render_template('auth/login.html')

    data = request.form if request.form else request.json
    if not data:
        flash("No input data provided", "error")
        return redirect(url_for('auth.login'))

    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()
    
    if not user or not user.check_password(password):
        flash("Invalid email or password.", "error")
        return redirect(url_for('auth.login'))
        
    login_user(user)
    flash("Login successful!", "success")
    return redirect('/dashboard')

@auth_bp.route('/logout', methods=['GET'])
@login_required
def logout():
    logout_user()
    session.pop('google_oauth_token', None)
    flash("You have been logged out.", "success")
    return redirect(url_for('auth.login'))

@auth_bp.route('/google', methods=['GET', 'POST'])
def google_auth():
    if not google.authorized:
        return redirect(url_for('google.login'))
        
    try:
        resp = google.get('/oauth2/v2/userinfo')
    except TokenExpiredError:
        return redirect(url_for('google.login'))
        
    try:
        if not resp.ok:
            flash("Failed to fetch user info from Google.", "error")
            return redirect(url_for('auth.login'))
            
        google_info = resp.json()
        email = google_info.get("email")
        name = google_info.get("name")
        
        if not email:
            flash("Could not get email from Google.", "error")
            return redirect(url_for('auth.login'))

        user = User.query.filter_by(email=email).first()
        
        if user:
            login_user(user)
            flash("Successfully logged in via Google.", "success")
        else:
            base_username = name.replace(" ", "").lower() if name else email.split('@')[0]
            if not base_username:
                base_username = "user"
                
            username = base_username
            counter = 1
            while User.query.filter_by(username=username).first():
                username = f"{base_username}{counter}"
                counter += 1
                
            new_user = User(
                email=email,
                username=username,
                is_google_user=True,
                account_type='student' # Default, will be updated via profile completion if needed
            )
            
            if "picture" in google_info:
                new_user.profile_picture = google_info["picture"]
                
            db.session.add(new_user)
            db.session.commit()
            
            login_user(new_user)
            flash("Account created! Please select your account type.", "success")
            return redirect(url_for('auth.complete_profile'))
            
        return redirect('/dashboard')
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"An error occurred during Google Auth: {str(e)}", "error")
        return redirect(url_for('auth.login'))

@auth_bp.route('/complete-profile', methods=['GET', 'POST'])
@login_required
def complete_profile():
    if request.method == 'GET':
        return render_template('auth/complete_profile.html')
        
    account_type = request.form.get('account_type')
    if account_type in ['student', 'mentor', 'team_leader']:
        current_user.account_type = account_type
        db.session.commit()
        flash("Profile completed successfully!", "success")
        return redirect('/dashboard')
        
    flash("Invalid account type selected.", "error")
    return redirect(url_for('auth.complete_profile'))
