from app import db
from app.models.notification import Notification

def create_notification(user_id, message, link=None):
    """
    Creates a Notification entry and broadcasts it via SocketIO.
    """
    from app import socketio
    
    notification = Notification(
        user_id=user_id,
        message=message,
        link=link
    )
    
    db.session.add(notification)
    db.session.commit()
    
    # Broadcast to user's personal room
    socketio.emit('new_notification', {
        'notification': notification.to_dict()
    }, room=f'user_{user_id}')
    
    return notification
