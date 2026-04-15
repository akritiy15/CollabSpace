from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from app.models.group import Group, GroupMember
from app.models.activity import ActivityLog
from app.utils.activity import ACTIVITY_CONFIG

activity_bp = Blueprint('activity', __name__, url_prefix='/groups/<int:group_id>/activity')

@activity_bp.url_value_preprocessor
def pull_group_id(endpoint, values):
    if values and 'group_id' in values:
        group_id = values.get('group_id')
        if current_user.is_authenticated:
            member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
            if not member:
                abort(403)

@activity_bp.route('/')
@login_required
def index(group_id):
    group = Group.query.get_or_404(group_id)
    filter_type = request.args.get('filter', 'all')
    
    query = ActivityLog.query.filter_by(group_id=group_id)
    
    if filter_type == 'tasks':
        query = query.filter(ActivityLog.action_type.in_(['TASK_CREATED', 'TASK_COMPLETED', 'TASK_DELETED', 'TASK_ASSIGNED']))
    elif filter_type == 'members':
        query = query.filter(ActivityLog.action_type.in_(['MEMBER_JOINED', 'MEMBER_LEFT', 'ROLE_CHANGED']))
        
    total_count = query.count()
    activities = query.order_by(ActivityLog.created_at.desc()).limit(20).all()
    
    return render_template(
        'activity/index.html',
        group=group,
        activities=activities,
        current_filter=filter_type,
        total_count=total_count,
        ACTIVITY_CONFIG=ACTIVITY_CONFIG
    )

@activity_bp.route('/feed')
@login_required
def feed(group_id):
    query = ActivityLog.query.filter_by(group_id=group_id)
    
    since = request.args.get('since')
    if since:
        pass # Optional robust filtering, mostly live socket pushes it anyway
        
    activities = query.order_by(ActivityLog.created_at.desc()).limit(20).all()
    
    data = []
    for a in activities:
        a_dict = a.to_dict()
        a_dict['username'] = a.user.username
        a_dict['user_avatar'] = a.user.profile_picture
        a_dict['config'] = ACTIVITY_CONFIG.get(a.action_type.lower())
        data.append(a_dict)
        
    return jsonify(data)
