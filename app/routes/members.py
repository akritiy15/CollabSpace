from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.models.user import User
from app.models.connection import MemberConnection
from app import db
from sqlalchemy import or_

members_bp = Blueprint('members', __name__, url_prefix='/members')

@members_bp.route('/')
@login_required
def index():
    sent_reqs = MemberConnection.query.filter_by(sender_id=current_user.id, status='pending').all()
    received_reqs = MemberConnection.query.filter_by(receiver_id=current_user.id, status='pending').all()
    
    connections = MemberConnection.query.filter(
        MemberConnection.status == 'accepted',
        or_(MemberConnection.sender_id == current_user.id, MemberConnection.receiver_id == current_user.id)
    ).all()
    
    friends = []
    for f in connections:
        if f.sender_id == current_user.id:
            friends.append(f.receiver)
        else:
            friends.append(f.sender)
            
    return render_template('members/index.html', 
        sent_reqs=sent_reqs, 
        received_reqs=received_reqs, 
        friends=friends
    )

@members_bp.route('/search')
@login_required
def search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
        
    existing_reqs = MemberConnection.query.filter(
        or_(MemberConnection.sender_id == current_user.id, MemberConnection.receiver_id == current_user.id)
    ).all()
    
    exclude_ids = [current_user.id]
    for r in existing_reqs:
        exclude_ids.append(r.sender_id if r.receiver_id == current_user.id else r.receiver_id)
        
    users = User.query.filter(
        ~User.id.in_(exclude_ids),
        or_(User.username.ilike(f"%{q}%"), User.email.ilike(f"%{q}%"))
    ).limit(10).all()
    
    results = []
    for u in users:
        results.append({
            'id': u.id,
            'username': u.username,
            'avatar': u.profile_picture or ''
        })
    return jsonify(results)

@members_bp.route('/request/<int:user_id>', methods=['POST'])
@login_required
def send_request(user_id):
    if user_id == current_user.id:
        return jsonify({'success': False, 'message': 'Cannot send request to yourself'})
        
    existing = MemberConnection.query.filter(
        or_(
            (MemberConnection.sender_id == current_user.id) & (MemberConnection.receiver_id == user_id),
            (MemberConnection.sender_id == user_id) & (MemberConnection.receiver_id == current_user.id)
        )
    ).first()
    
    if existing:
        return jsonify({'success': False, 'message': 'Request or connection already exists'})
        
    req = MemberConnection(sender_id=current_user.id, receiver_id=user_id)
    db.session.add(req)
    db.session.commit()
    return jsonify({'success': True})

@members_bp.route('/accept/<int:request_id>', methods=['POST'])
@login_required
def accept_request(request_id):
    req = MemberConnection.query.get_or_404(request_id)
    if req.receiver_id != current_user.id or req.status != 'pending':
        return jsonify({'success': False, 'message': 'Invalid request'})
        
    req.status = 'accepted'
    db.session.commit()
    return jsonify({'success': True})

@members_bp.route('/reject/<int:request_id>', methods=['POST'])
@login_required
def reject_request(request_id):
    req = MemberConnection.query.get_or_404(request_id)
    if req.receiver_id != current_user.id or req.status != 'pending':
        return jsonify({'success': False, 'message': 'Invalid request'})
        
    db.session.delete(req)
    db.session.commit()
    return jsonify({'success': True})

@members_bp.route('/remove/<int:user_id>', methods=['POST'])
@login_required
def remove_friend(user_id):
    req = MemberConnection.query.filter(
        MemberConnection.status == 'accepted',
        or_(
            (MemberConnection.sender_id == current_user.id) & (MemberConnection.receiver_id == user_id),
            (MemberConnection.sender_id == user_id) & (MemberConnection.receiver_id == current_user.id)
        )
    ).first()
    if not req:
        return jsonify({'success': False, 'message': 'Not connected'})
        
    db.session.delete(req)
    db.session.commit()
    return jsonify({'success': True})
