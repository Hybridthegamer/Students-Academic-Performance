"""
Seed script — populates the database with demo accounts + sample academic data
so the system works out-of-the-box after setup.
"""

from datetime import datetime, timezone
from app.models import User, Student, Lecturer, Course, AcademicRecord


def seed_demo_data(app, db):
    with app.app_context():
        if User.query.filter_by(email='admin@sapes.edu.ng').first():
            print('Database already seeded. Skipping.')
            return

        # ── Admin ─────────────────────────────────────────────────────────
        admin = User(username='admin', email='admin@sapes.edu.ng',
                     role='admin', full_name='System Administrator')
        admin.set_password('admin123')
        db.session.add(admin)

        # ── Lecturers ──────────────────────────────────────────────────────
        lec1_user = User(username='dr.ibrahim', email='ibrahim@sapes.edu.ng',
                         role='lecturer', full_name='Dr. Aminu Ibrahim')
        lec1_user.set_password('lecturer123')
        db.session.add(lec1_user)
        db.session.flush()

        lec1 = Lecturer(user_id=lec1_user.id, staff_id='LEC/CS/001',
                        department='Computer Science', designation='Senior Lecturer')
        db.session.add(lec1)

        lec2_user = User(username='mrs.okonkwo', email='okonkwo@sapes.edu.ng',
                         role='lecturer', full_name='Mrs. Ngozi Okonkwo')
        lec2_user.set_password('lecturer123')
        db.session.add(lec2_user)
        db.session.flush()

        lec2 = Lecturer(user_id=lec2_user.id, staff_id='LEC/CS/002',
                        department='Computer Science', designation='Lecturer I')
        db.session.add(lec2)
        db.session.flush()

        # ── Courses ────────────────────────────────────────────────────────
        courses_data = [
            ('CSC301', 'Data Structures and Algorithms', 3, 300, 'First', '2023/2024', lec1.id),
            ('CSC302', 'Operating Systems', 3, 300, 'First', '2023/2024', lec1.id),
            ('CSC303', 'Database Management Systems', 3, 300, 'Second', '2023/2024', lec2.id),
            ('CSC201', 'Discrete Mathematics', 2, 200, 'First', '2022/2023', lec1.id),
            ('CSC202', 'Introduction to Programming', 3, 200, 'First', '2022/2023', lec2.id),
        ]

        course_objs = []
        for code, name, cu, level, sem, sess, lid in courses_data:
            c = Course(code=code, name=name, credit_units=cu, department='Computer Science',
                       level=level, semester=sem, session=sess, lecturer_id=lid)
            db.session.add(c)
            course_objs.append(c)
        db.session.flush()

        # ── Students ───────────────────────────────────────────────────────
        students_seed = [
            ('stu001@sapes.edu.ng', 'stu001', 'student123', 'Emeka Obi', 'CSC/2021/001', 'Male', 300),
            ('stu002@sapes.edu.ng', 'stu002', 'student123', 'Amaka Eze', 'CSC/2021/002', 'Female', 300),
            ('stu003@sapes.edu.ng', 'stu003', 'student123', 'Bashir Musa', 'CSC/2021/003', 'Male', 300),
            ('stu004@sapes.edu.ng', 'stu004', 'student123', 'Fatima Suleiman', 'CSC/2021/004', 'Female', 300),
            ('stu005@sapes.edu.ng', 'stu005', 'student123', 'Chidi Nwosu', 'CSC/2021/005', 'Male', 300),
        ]

        student_objs = []
        for email, username, pwd, name, matric, gender, level in students_seed:
            u = User(username=username, email=email, role='student', full_name=name)
            u.set_password(pwd)
            db.session.add(u)
            db.session.flush()
            s = Student(user_id=u.id, matric_number=matric, department='Computer Science',
                        faculty='Computing & Technology', level=level, gender=gender)
            db.session.add(s)
            student_objs.append(s)
        db.session.flush()

        # ── Academic Records (CSC301 + CSC302 for all students) ────────────
        scores = [
            # (ca_score, exam_score, attendance) — per student
            (25, 60, 88),   # Emeka  — Good
            (28, 65, 92),   # Amaka  — Excellent
            (12, 30, 45),   # Bashir — At-Risk
            (22, 50, 78),   # Fatima — Average
            (26, 58, 85),   # Chidi  — Good
        ]

        for i, student in enumerate(student_objs):
            ca, exam, attend = scores[i]
            for course in course_objs[:3]:
                rec = AcademicRecord(
                    student_id=student.id, course_id=course.id,
                    ca_score=ca, exam_score=exam,
                    total_score=ca + exam,
                    attendance_percentage=attend,
                    semester=course.semester, session=course.session,
                )
                rec.save_computed_grade()
                db.session.add(rec)

        db.session.commit()
        print('Demo data seeded successfully.')
        print()
        print('  Admin   : admin@sapes.edu.ng / admin123')
        print('  Student : stu001@sapes.edu.ng / student123')
        print('  Lecturer: ibrahim@sapes.edu.ng / lecturer123')
