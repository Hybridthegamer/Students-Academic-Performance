import json
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from . import lecturer
from .. import db
from ..models import Lecturer, Course, AcademicRecord, Student, PerformanceResult, User
from ..utils.helpers import role_required, get_unread_notification_count


@lecturer.route('/dashboard')
@login_required
@role_required('lecturer')
def dashboard():
    lec = current_user.lecturer_profile
    if not lec:
        flash('Lecturer profile not found.', 'danger')
        return redirect(url_for('auth.login'))

    courses = lec.courses
    unread = get_unread_notification_count(current_user)

    # Students across lecturer's courses
    enrolled_student_ids = set()
    for c in courses:
        ids = db.session.query(AcademicRecord.student_id).filter_by(course_id=c.id).all()
        enrolled_student_ids.update(i[0] for i in ids)

    total_enrolled = len(enrolled_student_ids)
    at_risk_count = PerformanceResult.query.filter(
        PerformanceResult.student_id.in_(enrolled_student_ids),
        PerformanceResult.classification == 'At-Risk',
    ).count()

    return render_template('lecturer/dashboard.html',
                           lecturer=lec,
                           courses=courses,
                           total_enrolled=total_enrolled,
                           at_risk_count=at_risk_count,
                           unread=unread)


@lecturer.route('/courses/<int:course_id>')
@login_required
@role_required('lecturer')
def course_detail(course_id):
    lec = current_user.lecturer_profile
    course = Course.query.get_or_404(course_id)

    if course.lecturer_id != lec.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('lecturer.dashboard'))

    records = AcademicRecord.query.filter_by(course_id=course_id).join(Student).all()

    grade_dist = {}
    for rec in records:
        grade_dist[rec.grade or 'N/A'] = grade_dist.get(rec.grade or 'N/A', 0) + 1

    return render_template('lecturer/course_detail.html',
                           course=course,
                           records=records,
                           grade_dist=grade_dist)


@lecturer.route('/courses/<int:course_id>/records/add', methods=['GET', 'POST'])
@login_required
@role_required('lecturer')
def add_score(course_id):
    lec = current_user.lecturer_profile
    course = Course.query.get_or_404(course_id)

    if course.lecturer_id != lec.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('lecturer.dashboard'))

    students = Student.query.join(User).order_by(User.full_name).all()

    if request.method == 'POST':
        try:
            student_id = int(request.form['student_id'])
            ca_score = float(request.form.get('ca_score', 0) or 0)
            exam_score = float(request.form.get('exam_score', 0) or 0)
            attendance = float(request.form.get('attendance_percentage', 75) or 75)
            semester = request.form['semester']
            session_val = request.form['session'].strip()

            existing = AcademicRecord.query.filter_by(
                student_id=student_id, course_id=course_id,
                semester=semester, session=session_val
            ).first()

            if existing:
                existing.ca_score = ca_score
                existing.exam_score = exam_score
                existing.total_score = ca_score + exam_score
                existing.attendance_percentage = attendance
                existing.save_computed_grade()
            else:
                record = AcademicRecord(
                    student_id=student_id, course_id=course_id,
                    ca_score=ca_score, exam_score=exam_score,
                    total_score=ca_score + exam_score,
                    attendance_percentage=attendance,
                    semester=semester, session=session_val,
                )
                record.save_computed_grade()
                db.session.add(record)

            db.session.commit()
            flash('Score recorded successfully.', 'success')
            return redirect(url_for('lecturer.course_detail', course_id=course_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')

    return render_template('lecturer/add_score.html', course=course, students=students)


@lecturer.route('/students')
@login_required
@role_required('lecturer')
def students():
    lec = current_user.lecturer_profile
    course_ids = [c.id for c in lec.courses]

    student_ids = db.session.query(AcademicRecord.student_id).filter(
        AcademicRecord.course_id.in_(course_ids)
    ).distinct().all()
    student_ids = [s[0] for s in student_ids]

    all_students = Student.query.filter(Student.id.in_(student_ids)).join(User).order_by(
        User.full_name
    ).all()

    return render_template('lecturer/students.html', students=all_students)


@lecturer.route('/students/<int:student_id>')
@login_required
@role_required('lecturer')
def view_student(student_id):
    student = Student.query.get_or_404(student_id)
    latest_result = student.performance_results.order_by(
        PerformanceResult.evaluated_at.desc()
    ).first()

    shap_data = {}
    if latest_result and latest_result.shap_values_json:
        try:
            shap_data = json.loads(latest_result.shap_values_json)
        except Exception:
            shap_data = {}

    return render_template('lecturer/view_student.html',
                           student=student,
                           latest_result=latest_result,
                           shap_data=shap_data)
