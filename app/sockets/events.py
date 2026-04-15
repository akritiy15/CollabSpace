from flask import request
from flask_login import current_user
from app import socketio
from app.models.group import GroupMember

# In-memory dict for online users tracking per group
online_users = {}

@socketio.on('join_group')
def on_join_group(data):
    if not current_user.is_authenticated:
        return
        
    group_id = data.get('group_id')
    if not group_id:
        return
        
    member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not member:
        return
        
    from flask_socketio import join_room
    room = f'group_{group_id}'
    join_room(room)
    
    # Track presence
    if group_id not in online_users:
        online_users[group_id] = set()
    online_users[group_id].add(current_user.id)
    
    # Store rooms the socket is in on the socket context
    rooms = getattr(request, 'group_rooms', set())
    rooms.add(group_id)
    request.group_rooms = rooms
    
    socketio.emit('presence_update', {'online_user_ids': list(online_users[group_id])}, room=room)

@socketio.on('leave_group')
def on_leave_group(data):
    if not current_user.is_authenticated:
        return
        
    group_id = data.get('group_id')
    if not group_id:
        return
        
    from flask_socketio import leave_room
    room = f'group_{group_id}'
    leave_room(room)
    
    # Untrack presence
    if group_id in online_users and current_user.id in online_users[group_id]:
        online_users[group_id].remove(current_user.id)
        socketio.emit('presence_update', {'online_user_ids': list(online_users[group_id])}, room=room)

@socketio.on('disconnect')
def on_disconnect():
    if current_user.is_authenticated:
        rooms = getattr(request, 'group_rooms', set())
        for group_id in rooms:
            if group_id in online_users and current_user.id in online_users[group_id]:
                online_users[group_id].remove(current_user.id)
                socketio.emit('presence_update', {'online_user_ids': list(online_users[group_id])}, room=f'group_{group_id}')

@socketio.on('new_activity')
def on_new_activity(data):
    pass # Managed by the python helper directly emitting to the room instead

@socketio.on('join_user_room')
def on_join_user_room():
    if not current_user.is_authenticated:
        return
    from flask_socketio import join_room
    user_room = f'user_{current_user.id}'
    join_room(user_room)

@socketio.on('join_mentor_rooms')
def on_join_mentor_rooms():
    if not current_user.is_authenticated:
        return
        
    if getattr(current_user, 'mentor_profile', None):
        from flask_socketio import join_room
        from app.models.mentor import MentorGroup
        assignments = MentorGroup.query.filter_by(mentor_id=current_user.mentor_profile.id).all()
        rooms = getattr(request, 'group_rooms', set())
        for a in assignments:
            join_room(f'group_{a.group_id}')
            rooms.add(a.group_id)
        request.group_rooms = rooms
