from app.models.user import User
from app.models.group import Group, GroupMember
from app.models.task import Task
from app.models.activity import (
    ActivityLog, TASK_CREATED, TASK_COMPLETED, TASK_DELETED,
    TASK_ASSIGNED, MEMBER_JOINED, MEMBER_LEFT, REPORT_GENERATED, ROLE_CHANGED,
    TIME_LOGGED
)
from app.models.connection import MemberConnection
from app.models.report import ReportLog
from app.models.notification import UserNotificationPrefs, Notification
from app.models.time_tracking import TimeLog, TaskEstimate
from app.models.mentor import MentorProfile
from app.models.meeting import MeetingNote
from app.models.score import StudentScore
from app.models.profile import StudentAcademicProfile
