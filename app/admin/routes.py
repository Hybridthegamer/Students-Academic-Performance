import csv
import io
import json
import os
from datetime import datetime, timezone

from flask import (
    render_template, redirect, url_for, flash, request,
    current_app, jsonify, send_file
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from . import admin
from .. import db
from ..models import User, Student, Lecturer, Course, AcademicRecord, PerformanceResult, Notification
from ..utils.helpers import (
    role_required, compute_student_aggregates, send_in_app_notification,
    get_unread_notification_count
)
from ..ml.model import predict_student, explain_prediction, is_model_ready


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'csv', 'xlsx', 'xls'}


@admin.route('/dashboard')
@login_required
@role_required('admin')
def dashboard():
    total_students = Student.query.count()
    total_lecturers = Lecturer.query.count()
    total_courses = Course.query.count()
    recent_results = PerformanceResult.query.order_by(
        PerformanceResult.evaluated_at.desc()
    ).limit(10).all()

    classification_counts = {
        label: PerformanceResult.query.filter_by(classification=label).count()
        for label in ['At-Risk', 'Average', 'Good', 'Excellent']
    }

    at_risk = PerformanceResult.query.filter_by(classification='At-Risk').order_by(
        PerformanceResult.evaluated_at.desc()
    ).limit(5).all()

    unread = get_unread_notification_count(current_user)
    model_ready = is_model_ready()

    return render_template('admin/dashboard.html',
                           total_students=total_students,
                           total_lecturers=total_lecturers,
                           total_courses=total_courses,
                           recent_results=recent_results,
                           classification_counts=classification_counts,
                           at_risk=at_risk,
                           unread=unread,
                           model_ready=model_ready)


# ── Student Management ─────────────────────────────────────────────────────────

@admin.route('/students')
@login_required
@role_required('admin')
def students():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    dept = request.args.get('department', '')

    q = Student.query
    if search:
        q = q.join(User).filter(
            User.full_name.ilike(f'%{search}%') |
            Student.matric_number.ilike(f'%{search}%')
        )
    if dept:
        q = q.filter(Student.department == dept)

    students_page = q.paginate(page=page, per_page=20, error_out=False)
    departments = db.session.query(Student.department).distinct().all()

    return render_template('admin/students.html',
                           students=students_page,
                           departments=[d[0] for d in departments],
                           search=search,
                           dept=dept)


@admin.route('/students/add', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def add_student():
    if request.method == 'POST':
        try:
            full_name = request.form['full_name'].strip()
            username = request.form['username'].strip()
            email = request.form['email'].strip()
            password = request.form['password']
            matric = request.form['matric_number'].strip()
            department = request.form['department'].strip()
            level = int(request.form['level'])
            gender = request.form['gender']
            faculty = request.form.get('faculty', '').strip()

            if User.query.filter_by(email=email).first():
                flash('Email already exists.', 'danger')
                return render_template('admin/add_student.html')
            if User.query.filter_by(username=username).first():
                flash('Username already taken.', 'danger')
                return render_template('admin/add_student.html')
            if Student.query.filter_by(matric_number=matric).first():
                flash('Matric number already exists.', 'danger')
                return render_template('admin/add_student.html')

            user = User(username=username, email=email, role='student', full_name=full_name)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()

            student = Student(
                user_id=user.id,
                matric_number=matric,
                department=department,
                faculty=faculty,
                level=level,
                gender=gender,
            )
            db.session.add(student)
            db.session.commit()
            flash(f'Student {full_name} registered successfully.', 'success')
            return redirect(url_for('admin.students'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')

    return render_template('admin/add_student.html')


@admin.route('/students/<int:student_id>')
@login_required
@role_required('admin')
def view_student(student_id):
    student = Student.query.get_or_404(student_id)
    records = student.academic_records.order_by(
        AcademicRecord.session.desc(), AcademicRecord.semester.desc()
    ).all()
    results = student.performance_results.order_by(
        PerformanceResult.evaluated_at.desc()
    ).all()
    aggregates = compute_student_aggregates(student)

    latest_result = results[0] if results else None
    shap_data = {}
    if latest_result and latest_result.shap_values_json:
        try:
            shap_data = json.loads(latest_result.shap_values_json)
        except Exception:
            shap_data = {}

    return render_template('admin/view_student.html',
                           student=student,
                           records=records,
                           results=results,
                           aggregates=aggregates,
                           latest_result=latest_result,
                           shap_data=shap_data)


@admin.route('/students/<int:student_id>/evaluate', methods=['POST'])
@login_required
@role_required('admin')
def evaluate_student(student_id):
    if not is_model_ready():
        flash('ML model is not trained yet. Please train the model first.', 'warning')
        return redirect(url_for('admin.view_student', student_id=student_id))

    student = Student.query.get_or_404(student_id)
    agg = compute_student_aggregates(student)

    label, risk_prob, proba_dict = predict_student(
        cgpa=agg['cgpa'],
        avg_ca=agg['avg_ca'],
        avg_exam=agg['avg_exam'],
        attendance=agg['attendance'],
        courses=agg['courses_count'],
        level=student.level,
        gender=student.gender,
        department=student.department,
    )

    shap_data = explain_prediction(
        cgpa=agg['cgpa'], avg_ca=agg['avg_ca'], avg_exam=agg['avg_exam'],
        attendance=agg['attendance'], courses=agg['courses_count'],
        level=student.level, gender=student.gender, department=student.department,
    )

    result = PerformanceResult(
        student_id=student.id,
        classification=label,
        risk_probability=risk_prob,
        cgpa=agg['cgpa'],
        avg_ca_score=agg['avg_ca'],
        avg_exam_score=agg['avg_exam'],
        attendance_rate=agg['attendance'],
        courses_registered=agg['courses_count'],
        level=student.level,
        shap_values_json=json.dumps(shap_data) if shap_data else None,
    )
    db.session.add(result)

    # Alert advisor if at-risk
    if label == 'At-Risk' or risk_prob >= current_app.config['RISK_THRESHOLD']:
        send_in_app_notification(
            user_id=current_user.id,
            title='At-Risk Student Detected',
            message=f'{student.user.full_name} ({student.matric_number}) is classified as '
                    f'"{label}" with a risk probability of {risk_prob:.1%}. Immediate advisory contact recommended.',
            notif_type='alert',
            related_student_id=student.id,
        )

    db.session.commit()
    flash(f'Evaluation complete: {student.user.full_name} classified as {label}.', 'success')
    return redirect(url_for('admin.view_student', student_id=student_id))


@admin.route('/students/<int:student_id>/records/add', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def add_record(student_id):
    student = Student.query.get_or_404(student_id)
    courses = Course.query.order_by(Course.code).all()

    if request.method == 'POST':
        try:
            course_id = int(request.form['course_id'])
            ca_score = float(request.form.get('ca_score', 0) or 0)
            exam_score = float(request.form.get('exam_score', 0) or 0)
            attendance = float(request.form.get('attendance_percentage', 75) or 75)
            semester = request.form['semester']
            session_val = request.form['session'].strip()

            total_score = ca_score + exam_score
            record = AcademicRecord(
                student_id=student.id,
                course_id=course_id,
                ca_score=ca_score,
                exam_score=exam_score,
                total_score=total_score,
                attendance_percentage=attendance,
                semester=semester,
                session=session_val,
            )
            record.save_computed_grade()
            db.session.add(record)
            db.session.commit()
            flash('Academic record added successfully.', 'success')
            return redirect(url_for('admin.view_student', student_id=student_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving record: {str(e)}', 'danger')

    return render_template('admin/add_record.html', student=student, courses=courses)


@admin.route('/students/upload', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def upload_students():
    if request.method == 'POST':
        f = request.files.get('file')
        if not f or f.filename == '':
            flash('No file selected.', 'danger')
            return render_template('admin/upload_students.html')
        if not _allowed_file(f.filename):
            flash('Only CSV and Excel files are supported.', 'danger')
            return render_template('admin/upload_students.html')

        try:
            import pandas as pd
            if f.filename.endswith('.csv'):
                df = pd.read_csv(f)
            else:
                df = pd.read_excel(f)

            added, skipped = 0, 0
            for _, row in df.iterrows():
                matric = str(row.get('matric_number', '')).strip()
                if not matric or Student.query.filter_by(matric_number=matric).first():
                    skipped += 1
                    continue

                email = str(row.get('email', f'{matric}@student.edu.ng')).strip()
                full_name = str(row.get('full_name', 'Unknown')).strip()
                username = matric.lower().replace('/', '')

                user = User(
                    username=username, email=email, role='student', full_name=full_name
                )
                user.set_password(matric)  # default password = matric number
                db.session.add(user)
                db.session.flush()

                student = Student(
                    user_id=user.id,
                    matric_number=matric,
                    department=str(row.get('department', 'Other')).strip(),
                    faculty=str(row.get('faculty', '')).strip(),
                    level=int(row.get('level', 100)),
                    gender=str(row.get('gender', 'Male')).strip(),
                )
                db.session.add(student)
                added += 1

            db.session.commit()
            flash(f'Upload complete: {added} students added, {skipped} skipped.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error processing file: {str(e)}', 'danger')

    return render_template('admin/upload_students.html')


# ── Bulk Evaluate ──────────────────────────────────────────────────────────────

@admin.route('/evaluate/all', methods=['POST'])
@login_required
@role_required('admin')
def evaluate_all():
    if not is_model_ready():
        flash('ML model is not trained yet.', 'warning')
        return redirect(url_for('admin.dashboard'))

    students = Student.query.all()
    evaluated, at_risk_count = 0, 0

    for student in students:
        agg = compute_student_aggregates(student)
        label, risk_prob, proba_dict = predict_student(
            cgpa=agg['cgpa'], avg_ca=agg['avg_ca'], avg_exam=agg['avg_exam'],
            attendance=agg['attendance'], courses=agg['courses_count'],
            level=student.level, gender=student.gender, department=student.department,
        )

        result = PerformanceResult(
            student_id=student.id,
            classification=label,
            risk_probability=risk_prob,
            cgpa=agg['cgpa'],
            avg_ca_score=agg['avg_ca'],
            avg_exam_score=agg['avg_exam'],
            attendance_rate=agg['attendance'],
            courses_registered=agg['courses_count'],
            level=student.level,
        )
        db.session.add(result)
        evaluated += 1
        if label == 'At-Risk':
            at_risk_count += 1

    db.session.commit()
    flash(f'Batch evaluation complete: {evaluated} students evaluated, {at_risk_count} flagged as At-Risk.', 'success')
    return redirect(url_for('admin.dashboard'))


# ── Courses ────────────────────────────────────────────────────────────────────

@admin.route('/courses')
@login_required
@role_required('admin')
def courses():
    all_courses = Course.query.order_by(Course.session.desc(), Course.code).all()
    return render_template('admin/courses.html', courses=all_courses)


@admin.route('/courses/add', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def add_course():
    lecturers = Lecturer.query.join(User).order_by(User.full_name).all()
    if request.method == 'POST':
        try:
            course = Course(
                code=request.form['code'].strip().upper(),
                name=request.form['name'].strip(),
                credit_units=int(request.form.get('credit_units', 3)),
                department=request.form.get('department', '').strip(),
                level=int(request.form.get('level', 100)),
                semester=request.form['semester'],
                session=request.form['session'].strip(),
                lecturer_id=int(request.form['lecturer_id']) if request.form.get('lecturer_id') else None,
            )
            db.session.add(course)
            db.session.commit()
            flash(f'Course {course.code} added.', 'success')
            return redirect(url_for('admin.courses'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    return render_template('admin/add_course.html', lecturers=lecturers)


# ── Lecturers ──────────────────────────────────────────────────────────────────

@admin.route('/lecturers')
@login_required
@role_required('admin')
def lecturers():
    all_lecturers = Lecturer.query.join(User).order_by(User.full_name).all()
    return render_template('admin/lecturers.html', lecturers=all_lecturers)


@admin.route('/lecturers/add', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def add_lecturer():
    if request.method == 'POST':
        try:
            full_name = request.form['full_name'].strip()
            username = request.form['username'].strip()
            email = request.form['email'].strip()
            password = request.form['password']
            staff_id = request.form['staff_id'].strip()
            department = request.form['department'].strip()

            if User.query.filter_by(email=email).first():
                flash('Email already exists.', 'danger')
                return render_template('admin/add_lecturer.html')

            user = User(username=username, email=email, role='lecturer', full_name=full_name)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()

            lecturer = Lecturer(
                user_id=user.id, staff_id=staff_id, department=department,
                faculty=request.form.get('faculty', '').strip(),
                designation=request.form.get('designation', '').strip(),
            )
            db.session.add(lecturer)
            db.session.commit()
            flash(f'Lecturer {full_name} added.', 'success')
            return redirect(url_for('admin.lecturers'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    return render_template('admin/add_lecturer.html')


# ── Reports ────────────────────────────────────────────────────────────────────

@admin.route('/reports')
@login_required
@role_required('admin')
def reports():
    dept_stats = db.session.query(
        Student.department,
        db.func.count(Student.id).label('total'),
    ).group_by(Student.department).all()

    classification_counts = {
        label: PerformanceResult.query.filter_by(classification=label).count()
        for label in ['At-Risk', 'Average', 'Good', 'Excellent']
    }

    return render_template('admin/reports.html',
                           dept_stats=dept_stats,
                           classification_counts=classification_counts)


@admin.route('/reports/export/csv')
@login_required
@role_required('admin')
def export_csv():
    results = db.session.query(PerformanceResult, Student, User).join(
        Student, PerformanceResult.student_id == Student.id
    ).join(User, Student.user_id == User.id).order_by(
        PerformanceResult.evaluated_at.desc()
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Matric Number', 'Full Name', 'Department', 'Level',
                     'CGPA', 'Avg CA', 'Avg Exam', 'Attendance %',
                     'Classification', 'Risk Probability', 'Evaluated At'])

    for result, student, user in results:
        writer.writerow([
            student.matric_number, user.full_name, student.department, student.level,
            result.cgpa, result.avg_ca_score, result.avg_exam_score, result.attendance_rate,
            result.classification, f'{result.risk_probability:.2%}',
            result.evaluated_at.strftime('%Y-%m-%d %H:%M') if result.evaluated_at else '',
        ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'sapes_report_{datetime.now().strftime("%Y%m%d_%H%M")}.csv',
    )


# ── Notifications ──────────────────────────────────────────────────────────────

@admin.route('/notifications')
@login_required
@role_required('admin')
def notifications():
    notifs = current_user.notifications.order_by(Notification.created_at.desc()).limit(50).all()
    for n in notifs:
        n.is_read = True
    db.session.commit()
    return render_template('admin/notifications.html', notifications=notifs)


# ── Model Management ───────────────────────────────────────────────────────────

@admin.route('/model/train', methods=['POST'])
@login_required
@role_required('admin')
def train_model():
    try:
        from ..ml.train import train as run_train
        model_dir = current_app.config['MODEL_DIR']
        os.makedirs(os.path.join(current_app.root_path, '..', 'data'), exist_ok=True)
        _, metrics = run_train(model_dir, verbose=False)
        flash(
            f'Model trained successfully! Accuracy: {metrics["accuracy"]:.1%}, '
            f'Macro F1: {metrics["macro_f1"]:.4f}',
            'success'
        )
    except Exception as e:
        flash(f'Training failed: {str(e)}', 'danger')
    return redirect(url_for('admin.dashboard'))


@admin.route('/model/metrics')
@login_required
@role_required('admin')
def model_metrics():
    metrics_path = os.path.join(current_app.config['MODEL_DIR'], 'model_metrics.json')
    metrics = {}
    if os.path.exists(metrics_path):
        with open(metrics_path) as fh:
            metrics = json.load(fh)
    return render_template('admin/model_metrics.html', metrics=metrics, model_ready=is_model_ready())
