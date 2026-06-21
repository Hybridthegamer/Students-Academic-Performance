from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from . import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.Enum('admin', 'lecturer', 'student', name='user_roles'), nullable=False)
    full_name = db.Column(db.String(128), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime)

    # Relationships
    student_profile = db.relationship('Student', back_populates='user', uselist=False)
    lecturer_profile = db.relationship('Lecturer', back_populates='user', uselist=False)
    notifications = db.relationship('Notification', back_populates='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Student(db.Model):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    matric_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    department = db.Column(db.String(100), nullable=False)
    faculty = db.Column(db.String(100))
    level = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.Enum('Male', 'Female', 'Other', name='gender_enum'), nullable=False)
    date_of_birth = db.Column(db.Date)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    entry_year = db.Column(db.Integer)
    family_income_bracket = db.Column(db.Enum('Low', 'Middle', 'High', name='income_bracket'))
    parental_education = db.Column(db.Enum('None', 'Primary', 'Secondary', 'Tertiary', name='edu_level'))

    user = db.relationship('User', back_populates='student_profile')
    academic_records = db.relationship('AcademicRecord', back_populates='student', lazy='dynamic')
    performance_results = db.relationship('PerformanceResult', back_populates='student', lazy='dynamic')

    def __repr__(self):
        return f'<Student {self.matric_number}>'


class Lecturer(db.Model):
    __tablename__ = 'lecturers'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    staff_id = db.Column(db.String(20), unique=True, nullable=False)
    department = db.Column(db.String(100), nullable=False)
    faculty = db.Column(db.String(100))
    designation = db.Column(db.String(100))

    user = db.relationship('User', back_populates='lecturer_profile')
    courses = db.relationship('Course', back_populates='lecturer')

    def __repr__(self):
        return f'<Lecturer {self.staff_id}>'


class Course(db.Model):
    __tablename__ = 'courses'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    credit_units = db.Column(db.Integer, nullable=False, default=3)
    department = db.Column(db.String(100))
    level = db.Column(db.Integer)
    semester = db.Column(db.Enum('First', 'Second', name='semester_enum'), nullable=False)
    session = db.Column(db.String(10), nullable=False)
    lecturer_id = db.Column(db.Integer, db.ForeignKey('lecturers.id'))

    lecturer = db.relationship('Lecturer', back_populates='courses')
    academic_records = db.relationship('AcademicRecord', back_populates='course', lazy='dynamic')

    def __repr__(self):
        return f'<Course {self.code}>'


class AcademicRecord(db.Model):
    __tablename__ = 'academic_records'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    ca_score = db.Column(db.Float)
    exam_score = db.Column(db.Float)
    total_score = db.Column(db.Float)
    grade = db.Column(db.String(2))
    grade_point = db.Column(db.Float)
    attendance_percentage = db.Column(db.Float)
    semester = db.Column(db.Enum('First', 'Second', name='rec_semester'), nullable=False)
    session = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))

    student = db.relationship('Student', back_populates='academic_records')
    course = db.relationship('Course', back_populates='academic_records')

    __table_args__ = (
        db.UniqueConstraint('student_id', 'course_id', 'semester', 'session', name='uq_student_course_semester'),
    )

    def compute_grade(self):
        score = self.total_score
        if score is None:
            return None, None
        if score >= 70:
            return 'A', 5.0
        elif score >= 60:
            return 'B', 4.0
        elif score >= 50:
            return 'C', 3.0
        elif score >= 45:
            return 'D', 2.0
        elif score >= 40:
            return 'E', 1.0
        else:
            return 'F', 0.0

    def save_computed_grade(self):
        grade, gp = self.compute_grade()
        self.grade = grade
        self.grade_point = gp

    def __repr__(self):
        return f'<AcademicRecord student={self.student_id} course={self.course_id}>'


class PerformanceResult(db.Model):
    __tablename__ = 'performance_results'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    classification = db.Column(db.Enum('At-Risk', 'Average', 'Good', 'Excellent', name='perf_class'), nullable=False)
    risk_probability = db.Column(db.Float, nullable=False)
    cgpa = db.Column(db.Float)
    avg_ca_score = db.Column(db.Float)
    avg_exam_score = db.Column(db.Float)
    attendance_rate = db.Column(db.Float)
    courses_registered = db.Column(db.Integer)
    level = db.Column(db.Integer)
    semester = db.Column(db.String(10))
    session = db.Column(db.String(10))
    shap_values_json = db.Column(db.Text)
    evaluated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    student = db.relationship('Student', back_populates='performance_results')

    def __repr__(self):
        return f'<PerformanceResult student={self.student_id} class={self.classification}>'


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.Enum('alert', 'info', 'success', 'warning', name='notif_type'), default='info')
    is_read = db.Column(db.Boolean, default=False)
    related_student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', back_populates='notifications')

    def __repr__(self):
        return f'<Notification {self.id} user={self.user_id}>'
