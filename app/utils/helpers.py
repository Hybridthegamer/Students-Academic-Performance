import json
from functools import wraps
from flask import abort
from flask_login import current_user
from ..models import Student, AcademicRecord, PerformanceResult, Notification
from .. import db


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


def compute_student_aggregates(student):
    """
    Compute CGPA and other aggregate metrics for a student
    from their AcademicRecord rows.
    Returns a dict with cgpa, avg_ca, avg_exam, attendance, courses_count.
    """
    records = student.academic_records.all()
    if not records:
        return {
            'cgpa': None, 'avg_ca': None, 'avg_exam': None,
            'attendance': None, 'courses_count': 0,
        }

    total_quality_points = 0.0
    total_credit_units = 0
    ca_scores, exam_scores, attendances = [], [], []

    for rec in records:
        if rec.grade_point is not None and rec.course and rec.course.credit_units:
            total_quality_points += rec.grade_point * rec.course.credit_units
            total_credit_units += rec.course.credit_units
        if rec.ca_score is not None:
            ca_scores.append(rec.ca_score)
        if rec.exam_score is not None:
            exam_scores.append(rec.exam_score)
        if rec.attendance_percentage is not None:
            attendances.append(rec.attendance_percentage)

    cgpa = round(total_quality_points / total_credit_units, 2) if total_credit_units > 0 else None
    return {
        'cgpa': cgpa,
        'avg_ca': round(sum(ca_scores) / len(ca_scores), 2) if ca_scores else None,
        'avg_exam': round(sum(exam_scores) / len(exam_scores), 2) if exam_scores else None,
        'attendance': round(sum(attendances) / len(attendances), 2) if attendances else None,
        'courses_count': len(records),
    }


def get_unread_notification_count(user):
    return Notification.query.filter_by(user_id=user.id, is_read=False).count()


def mark_notifications_read(user):
    Notification.query.filter_by(user_id=user.id, is_read=False).update({'is_read': True})
    db.session.commit()


def send_in_app_notification(user_id, title, message, notif_type='info', related_student_id=None):
    notif = Notification(
        user_id=user_id,
        title=title,
        message=message,
        type=notif_type,
        related_student_id=related_student_id,
    )
    db.session.add(notif)
    db.session.commit()
    return notif


def get_performance_badge_class(classification):
    return {
        'Excellent': 'success',
        'Good': 'primary',
        'Average': 'warning',
        'At-Risk': 'danger',
    }.get(classification, 'secondary')
