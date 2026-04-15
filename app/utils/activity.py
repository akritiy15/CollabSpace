from app import db
from app.models.activity import ActivityLog

MEETING_ANALYZED = 'meeting_analyzed'

ACTIVITY_CONFIG = {
    'task_created':   {'icon': 'circle-plus',   'color': 'blue',   'label': 'created task'},
    'task_completed': {'icon': 'circle-check',  'color': 'green',  'label': 'completed task'},
    'task_deleted':   {'icon': 'circle-minus',  'color': 'red',    'label': 'deleted task'},
    'task_assigned':  {'icon': 'user-check',    'color': 'blue',   'label': 'assigned task'},
    'member_joined':  {'icon': 'user-plus',     'color': 'green',  'label': 'joined the group'},
    'member_left':    {'icon': 'user-minus',    'color': 'gray',   'label': 'left the group'},
    'report_generated':{'icon': 'file-text',    'color': 'gray',   'label': 'generated a report'},
    'role_changed':   {'icon': 'shield',        'color': 'amber',  'label': 'role was changed'},
    'time_logged':    {'icon': 'clock',         'color': 'blue',   'label': 'logged time on a task'},
    'meeting_analyzed':{'icon': 'notebook',     'color': 'purple', 'label': 'analyzed meeting notes'},
}

def log_activity(group_id, user_id, action_type, description, metadata=None):
    """
    Creates an ActivityLog entry, commits it to the database,
    and broadcasts it to the group via SocketIO.
    """
    from app import socketio  # Import here to avoid circular imports if necessary
    
    if metadata is None:
        metadata = {}
        
    activity = ActivityLog(
        group_id=group_id,
        user_id=user_id,
        action_type=action_type,
        description=description,
        meta_data=metadata
    )
    
    db.session.add(activity)
    db.session.commit()
    
    # Broadcast to SocketIO
    config = ACTIVITY_CONFIG.get(action_type.lower(), {'icon': 'activity', 'color': 'gray', 'label': 'performed an action'})
    
    activity_dict = activity.to_dict()
    activity_dict['username'] = activity.user.username if activity.user else 'Unknown'
    activity_dict['user_avatar'] = activity.user.profile_picture if activity.user and getattr(activity.user, 'profile_picture', None) else None
    
    socketio.emit('activity_update', {
        'activity': activity_dict,
        'config': config
    }, room=f'group_{group_id}')
    
    if action_type.lower() in ['task_completed', 'time_logged']:
        from app.utils.score import calculate_student_score
        from app.models.task import Task
        target_student_id = user_id
        if metadata and 'task_id' in metadata:
            t = Task.query.get(metadata['task_id'])
            if t and t.assigned_to:
                target_student_id = t.assigned_to
        
        if target_student_id:
            try:
                calculate_student_score(target_student_id, group_id)
            except Exception as e:
                import logging
                logging.error(f"Failed to calculate score: {e}")
    
    return activity
