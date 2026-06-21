import json
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from . import student
from ..models import Student, AcademicRecord, PerformanceResult, Notification
from ..utils.helpers import role_required, compute_student_aggregates, get_unread_notification_count
from .. import db


@student.route('/dashboard')
@login_required
@role_required('student')
def dashboard():
    profile = current_user.student_profile
    if not profile:
        flash('Student profile not found. Contact your administrator.', 'danger')
        return redirect(url_for('auth.login'))

    aggregates = compute_student_aggregates(profile)
    latest_result = profile.performance_results.order_by(
        PerformanceResult.evaluated_at.desc()
    ).first()

    recent_records = profile.academic_records.order_by(
        AcademicRecord.session.desc(), AcademicRecord.semester.desc()
    ).limit(8).all()

    unread = get_unread_notification_count(current_user)

    shap_data = {}
    if latest_result and latest_result.shap_values_json:
        try:
            shap_data = json.loads(latest_result.shap_values_json)
        except Exception:
            shap_data = {}

    return render_template('student/dashboard.html',
                           profile=profile,
                           aggregates=aggregates,
                           latest_result=latest_result,
                           recent_records=recent_records,
                           shap_data=shap_data,
                           unread=unread)


@student.route('/records')
@login_required
@role_required('student')
def records():
    profile = current_user.student_profile
    all_records = profile.academic_records.order_by(
        AcademicRecord.session.desc(), AcademicRecord.semester.desc()
    ).all()
    return render_template('student/records.html', records=all_records, profile=profile)


@student.route('/performance-history')
@login_required
@role_required('student')
def performance_history():
    profile = current_user.student_profile
    results = profile.performance_results.order_by(
        PerformanceResult.evaluated_at.asc()
    ).all()
    return render_template('student/performance_history.html', results=results, profile=profile)


@student.route('/notifications')
@login_required
@role_required('student')
def notifications():
    notifs = current_user.notifications.order_by(Notification.created_at.desc()).limit(30).all()
    for n in notifs:
        n.is_read = True
    db.session.commit()
    return render_template('student/notifications.html', notifications=notifs)
