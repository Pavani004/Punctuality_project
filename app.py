import csv
import os
import random
# Use pymysql as a MySQL driver
import pymysql
pymysql.install_as_MySQLdb()
import json

import requests
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from datetime import datetime, date, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import smtplib
from email.mime.text import MIMEText
from werkzeug.security import generate_password_hash, check_password_hash
from flask.json import jsonify
from sqlalchemy import and_
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import SubmitField
import atexit

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:KARTHIK%402004@localhost/lateattendance'
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'

# Create uploads directory if it doesn't exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Form for file upload
class UploadForm(FlaskForm):
    file = FileField('CSV File', validators=[
        FileRequired(),
        FileAllowed(['csv'], 'Only CSV files are allowed!')
    ])
    submit = SubmitField('Upload')

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Models
class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    # Flask-Login required attributes and methods
    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    
class Student(db.Model):
    __tablename__ = 'student'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    roll_no = db.Column(db.String(20), unique=True)
    year = db.Column(db.String(50))
    department = db.Column(db.String(50))
    section = db.Column(db.String(1))
    parent_email = db.Column(db.String(100))
    parent_mobile = db.Column(db.String(15))
    late_count = db.Column(db.Integer, default=0, nullable=False)
    week_late_count = db.Column(db.Integer, default=0, nullable=False)
    month_late_count = db.Column(db.Integer, default=0, nullable=False)

    def __init__(self, name, roll_no, year, department, section, parent_email, parent_mobile, late_count=0, week_late_count=0, month_late_count=0):
        self.name = name
        self.roll_no = roll_no
        self.year = year
        self.department = department
        self.section = section
        self.parent_email = parent_email
        self.parent_mobile = parent_mobile
        self.late_count = late_count
        self.week_late_count = week_late_count
        self.month_late_count = month_late_count


class DisciplineIncharge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(100), nullable=False)

class Faculty(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    section = db.Column(db.String(1), nullable=False)
    password = db.Column(db.String(100), nullable=False)

    def get_id(self):
        return str(self.id)

class HOD(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(100), nullable=False)

    def get_id(self):
        return str(self.id)

class Principal(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(100), nullable=False)

    def get_id(self):
        return str(self.id)

class LateAttendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    date = db.Column(db.Date, nullable=False)
    student = db.relationship('Student', backref='late_attendance_records')

@login_manager.user_loader
def load_user(user_id):
    # Load user from any role
    user = Student.query.get(int(user_id)) or Faculty.query.get(int(user_id)) or \
           HOD.query.get(int(user_id)) or Principal.query.get(int(user_id)) or Admin.query.get(int(user_id))
    return user

def reset_attendance_counts():
    today = datetime.now()
    
    # Reset weekly counts on Monday
    if today.weekday() == 0:  # Monday
        students = Student.query.all()
        for student in students:
            student.week_late_count = 0
    
    # Reset monthly counts on the first day of the month
    if today.day == 1:  # First day of the month
        students = Student.query.all()
        for student in students:
            student.month_late_count = 0
    
    # Calculate current week's late count
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    # Calculate current month's late count
    start_of_month = today.replace(day=1)
    end_of_month = (start_of_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    students = Student.query.all()
    for student in students:
        # Update weekly count
        week_late_count = LateAttendance.query.filter(
            LateAttendance.student_id == student.id,
            LateAttendance.date >= start_of_week.date(),
            LateAttendance.date <= end_of_week.date()
        ).count()
        student.week_late_count = week_late_count
        
        # Update monthly count
        month_late_count = LateAttendance.query.filter(
            LateAttendance.student_id == student.id,
            LateAttendance.date >= start_of_month.date(),
            LateAttendance.date <= end_of_month.date()
        ).count()
        student.month_late_count = month_late_count
    
    db.session.commit()

# Start the scheduler
scheduler = BackgroundScheduler()
# Run at midnight every day
scheduler.add_job(func=reset_attendance_counts, trigger="cron", hour=0, minute=0)
scheduler.start()

# Ensure the scheduler shuts down when the app stops
atexit.register(lambda: scheduler.shutdown())

# Load students from CSV
def load_students_from_csv(file_path):
    print(f"Loading students from: {file_path}")
    
    if not os.path.exists(file_path):
        flash('File not found. Please upload a valid CSV file.', 'danger')
        return
    
    try:
        with open(file_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            
            # Define expected headers from the CSV
            expected_headers = {'name', 'roll_no', 'year', 'department', 'section', 'parent_email', 'parent_mobile'}
            if not expected_headers.issubset(reader.fieldnames):
                flash('CSV headers do not match the expected format.', 'danger')
                return
            
            students = []
            for row in reader:
                print(f"Processing row: {row}")
                # Clean and standardize roll number
                roll_no = row['roll_no'].strip().upper()  # Convert to uppercase and remove spaces
                
                # Check if student already exists
                existing_student = Student.query.filter_by(roll_no=roll_no).first()
                if existing_student:
                    print(f"Student with roll number {roll_no} already exists. Skipping.")
                    continue
                
                # Prepare data for insertion using SQLAlchemy
                student = Student(
                    name=row['name'].strip(),
                    roll_no=roll_no,
                    year=row['year'].strip(),
                    department=row['department'].strip(),
                    section=row['section'].strip(),
                    parent_email=row['parent_email'].strip(),
                    parent_mobile=row['parent_mobile'].strip(),
                    late_count=0,
                    week_late_count=0,
                    month_late_count=0
                )
                students.append(student)
                print(f"Added student: {student.name} (Roll No: {student.roll_no})")

            if students:
                db.session.add_all(students)  # Add all student objects to the session
                db.session.commit()  # Commit to save to the database
                flash(f'Successfully loaded {len(students)} students from CSV.', 'success')
            else:
                flash('No new students found in CSV.', 'warning')
    
    except Exception as e:
        print(f"Error: {e}")
        db.session.rollback()  # Rollback in case of error
        flash(f'Failed to load students. Error: {e}', 'danger')

@app.route('/')
def index():
    return render_template('index.html', title="Late Attendance System")

# Route for Student Login
@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Validate Student credentials
        student = Student.query.filter_by(roll_no=username).first()
        if student and student.roll_no == password:
            login_user(student)
            return redirect(url_for('student_dashboard'))

        # Invalid credentials
        flash('Invalid login credentials', 'danger')
    
    return render_template('student_login.html', title="Student Login")

# Route for Shared Login for all other roles
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Validate Discipline Incharge
        discipline_incharge = DisciplineIncharge.query.filter_by(name=username).first()
        if discipline_incharge and discipline_incharge.password == password:
            session['user_type'] = 'DisciplineIncharge'
            return redirect(url_for('discipline_incharge_dashboard'))

        # Validate Faculty
        faculty = Faculty.query.filter_by(name=username).first()
        if faculty and faculty.password == password:
            login_user(faculty)
            session['user_type'] = 'Faculty'
            return redirect(url_for('faculty_dashboard'))

        # Validate HOD
        hod = HOD.query.filter_by(name=username).first()
        if hod and hod.password == password:
            login_user(hod)
            session['user_type'] = 'HOD'
            return redirect(url_for('hod_dashboard'))

        # Validate Principal
        principal = Principal.query.filter_by(name=username).first()
        if principal and principal.password == password:
            login_user(principal)
            session['user_type'] = 'Principal'
            return redirect(url_for('principal_dashboard'))

        # Validate Admin
        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.password == password:
            login_user(admin)
            session['user_type'] = 'Admin'
            return redirect(url_for('admin_dashboard'))

        # Invalid credentials
        flash('Invalid login credentials', 'danger')

    return render_template('login.html', title="Login")


@app.route('/logout')
def logout():
    session.clear()
    logout_user()
    return redirect(url_for('index'))

@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if session.get('user_type') != 'Admin':
        return redirect(url_for('index'))

    return render_template('admin_dashboard.html')
@app.route('/student_dashboard')
@login_required
def student_dashboard():
    student = current_user
    late_records = LateAttendance.query.filter_by(student_id=student.id).all()
    return render_template('student_dashboard.html', student=student, late_records=late_records, title="Student Dashboard")

@app.route('/discipline_incharge_register', methods=['GET', 'POST'])
def discipline_incharge_register():
    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']
        new_incharge = DisciplineIncharge(name=name, password=password)
        db.session.add(new_incharge)
        db.session.commit()
        flash('Discipline Incharge registered successfully', 'success')
        return redirect(url_for('index'))
    return render_template('discipline_incharge_register.html', title="Discipline Incharge Register")

from flask import render_template, request, jsonify, flash
from datetime import date


@app.route('/discipline_incharge_dashboard', methods=['GET', 'POST'])
def discipline_incharge_dashboard():
    today = date.today()

    # Handle AJAX POST request
    if request.method == 'POST':
        roll_no = request.form['roll_no'].strip()
        
        # Debug logging
        print(f"Searching for student with roll number: {roll_no}")
        
        # Try to find the student
        student = Student.query.filter_by(roll_no=roll_no).first()
        
        # Debug logging
        if student:
            print(f"Found student: {student.name} (Roll No: {student.roll_no})")
        else:
            print(f"No student found with roll number: {roll_no}")
            # List all students for debugging
            all_students = Student.query.all()
            print("Available students:")
            for s in all_students:
                print(f"- {s.roll_no}: {s.name}")

        if not student:
            return jsonify(success=False, message='Student not found. Please check the roll number.')

        existing_record = LateAttendance.query.filter_by(student_id=student.id, date=today).first()
        if existing_record:
            return jsonify(success=False, message='Student has already been marked late today.')

        late_record = LateAttendance(student_id=student.id, date=today)
        db.session.add(late_record)

        # Initialize counts if they are None
        if student.late_count is None:
            student.late_count = 0
        if student.week_late_count is None:
            student.week_late_count = 0
        if student.month_late_count is None:
            student.month_late_count = 0

        # Increment counts
        student.late_count += 1
        student.week_late_count += 1
        student.month_late_count += 1
        db.session.commit()

        if student.late_count % 3 == 0:
            send_email_notification(student.parent_email, student.name)
            send_sms_notification(student.parent_mobile, student.name)

        # Return updated student data for table
        return jsonify(success=True, message=f"{student.name} marked late for today.", student={
            'name': student.name,
            'roll_no': student.roll_no,
            'year': student.year,
            'department': student.department,
            'total_late': student.late_count,
            'late_this_week': student.week_late_count,
            'late_this_month': student.month_late_count,
            'record_id': late_record.id
        })

    # For GET request, render the page
    late_records_today = LateAttendance.query.filter_by(date=today).all()
    students = []

    for record in late_records_today:
        student = Student.query.get(record.student_id)
        if student:
            students.append({
                'name': student.name,
                'roll_no': student.roll_no,
                'year': student.year,
                'department': student.department,
                'total_late': student.late_count,
                'late_this_week': student.week_late_count,
                'late_this_month': student.month_late_count,
                'record_id': record.id
            })

    return render_template('discipline_incharge.html', title="Discipline In-Charge Dashboard", students=students, today=today)
@app.route('/delete_late_record/<int:record_id>', methods=['POST'])
def delete_late_record(record_id):
    record = LateAttendance.query.get(record_id)
    if record:
        student = Student.query.get(record.student_id)
        if student:
            # Decrement the counts
            student.late_count = max(0, student.late_count - 1)
            student.week_late_count = max(0, student.week_late_count - 1)
            student.month_late_count = max(0, student.month_late_count - 1)
            db.session.delete(record)
            db.session.commit()
            flash('Today\'s late attendance record deleted successfully.', 'success')
        else:
            flash('Student not found.', 'danger')
    else:
        flash('Record not found.', 'danger')
    return redirect(url_for('discipline_incharge_dashboard'))

# Route to view previous days' late attendance
@app.route('/view_previous_attendance', methods=['GET', 'POST'])
def view_previous_attendance():
    # Handle the selected date from the form
    selected_date = request.form.get('selected_date')
    
    if selected_date:
        selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
    else:
        # Default to yesterday
        selected_date = date.today() - timedelta(days=1)

    # Fetch records for the selected date
    records = LateAttendance.query.filter(LateAttendance.date == selected_date).all()

    # Prepare data for display
    students = []
    for record in records:
        student = Student.query.get(record.student_id)
        if student:
            students.append({
                'name': student.name,
                'roll_no': student.roll_no,
                'year': student.year,
                'department': student.department,
                'section': student.section,
                'parent_email': student.parent_email,
                'parent_mobile': student.parent_mobile,
                'date': record.date,
                'record_id': record.id
            })

    return render_template(
        'view_previous_attendance.html',
        title="Previous Late Attendance",
        students=students,
        selected_date=selected_date
    )


@app.route('/faculty_register', methods=['GET', 'POST'])
def faculty_register():
    if request.method == 'POST':
        name = request.form['name']
        department = request.form['department']
        year = request.form['year']
        section = request.form['section']
        password = request.form['password']
        new_faculty = Faculty(name=name, department=department, year=year, section=section, password=password)
        db.session.add(new_faculty)
        db.session.commit()
        flash('Faculty registered successfully', 'success')
        return redirect(url_for('index'))
    return render_template('faculty_register.html', title="Faculty Register")

@app.route('/faculty_dashboard', methods=['GET'])
@login_required
def faculty_dashboard():
    # Check if the logged-in user is a faculty member
    if session.get('user_type') != 'Faculty':
        return redirect(url_for('index'))
    
    # Retrieve the faculty member's details
    faculty = Faculty.query.get(current_user.id)
    if not faculty:
        flash("Faculty member not found!", "danger")
        return redirect(url_for('index'))

    # Extract faculty details
    department = faculty.department
    year = faculty.year
    section = faculty.section
    name = faculty.name

    # Fetch students from the faculty's department, year, and section
    students = Student.query.filter_by(department=department, year=year, section=section).all()

    # Get today's date and the start and end of the current week
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    week_dates = [start_of_week + timedelta(days=i) for i in range(7)]

    # Collect late attendance data for the week
    attendance_data = []
    total_late_students_today = 0

    for student in students:
        week_status = []
        lifetime_late_count = LateAttendance.query.filter_by(student_id=student.id).count()  # Total lifetime late count

        # Check each date in the week
        for day in week_dates:
            record = LateAttendance.query.filter_by(student_id=student.id, date=day).first()
            week_status.append('Yes' if record else 'No')

        # Increment today's late count if the student is late today
        if LateAttendance.query.filter_by(student_id=student.id, date=today).first():
            total_late_students_today += 1

        attendance_data.append({
            'roll_no': student.roll_no,
            'name': student.name,
            'week_status': week_status,
            'lifetime_late_count': lifetime_late_count
        })

    # Filter late students for today
    late_students_today = [student for student in students if LateAttendance.query.filter_by(student_id=student.id, date=today).first()]

    return render_template(
        'faculty_dashboard.html',
        faculty_name=name,
        department=department,
        year=year,
        section=section,
        today=today,
        start_of_week=start_of_week,
        end_of_week=end_of_week,
        week_dates=week_dates,
        attendance_data=attendance_data,
        late_students_today=late_students_today,
        total_late_students_today=total_late_students_today,
        title="Faculty Dashboard"
    )



# HOD Registration and Dashboard
@app.route('/hod_register', methods=['GET', 'POST'])
def hod_register():
    if request.method == 'POST':
        name = request.form['name']
        department = request.form['department']
        password = request.form['password']
        new_hod = HOD(name=name, department=department, password=password)
        db.session.add(new_hod)
        db.session.commit()
        flash('HOD registered successfully', 'success')
        return redirect(url_for('index'))
    return render_template('hod_register.html', title="HOD Register", departments=["CSE", "ECE", "IT", "CSE-DS", "CSE-AIML", "CS-AIDS", "H&S"])


@app.route('/hod_dashboard', methods=['GET', 'POST'])
@login_required
def hod_dashboard():
    # Check user type
    if session.get('user_type') != 'HOD':
        return redirect(url_for('index'))

    hod = HOD.query.get(current_user.id)
    if not hod:
        flash("HOD not found!", "danger")
        return redirect(url_for('index'))

    department = hod.department

    # Handle the date filter for the calendar
    selected_date = date.today()
    if request.method == 'POST':
        date_str = request.form.get('date')
        if date_str:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
    # Special handling for H&S (First Year)
    if department == "H&S":
        all_departments = ["CSE", "ECE", "IT", "CSE-DS", "CSE-AIML", "CS-AIDS"]
        all_sections = ["A", "B", "C", "D", "E", "F", "G", "H"]
        attendance_summary = {dept: {section: 0 for section in all_sections} for dept in all_departments}
        late_students_detail = {dept: {section: [] for section in all_sections} for dept in all_departments}

        # Fetch first-year students from H&S
        students = Student.query.filter_by(year='H&S').all()  # Use 'H&S' for first-year students

        for student in students:
            student_dept = student.department
            section = student.section
            if student_dept in all_departments and section in all_sections:
                # Fetch late attendance for today
                late_count = LateAttendance.query.filter_by(student_id=student.id, date=selected_date).count()
                if late_count > 0:
                    attendance_summary[student_dept][section] += 1
                    late_students_detail[student_dept][section].append({
                        'roll_no': student.roll_no,
                        'name': student.name,
                        'late_count':student.late_count
                    })
    else:
        # Regular HOD logic for other departments (Years 2, 3, 4)
        all_years = [2, 3, 4]
        all_sections = ["A", "B", "C", "D", "E", "F", "G", "H"]
        attendance_summary = {year: {section: 0 for section in all_sections} for year in all_years}
        late_students_detail = {year: {section: [] for section in all_sections} for year in all_years}

        students = Student.query.filter_by(department=department).all()
        for student in students:
            year = student.year
            section = student.section
            if year in all_years and section in all_sections:
                # Fetch late attendance for today
                late_count = LateAttendance.query.filter_by(student_id=student.id, date=selected_date).count()
                if late_count > 0:
                    attendance_summary[year][section] += 1
                    late_students_detail[year][section].append({
                        'roll_no': student.roll_no,
                        'name': student.name
                    })

    return render_template(
        'hod_dashboard.html',
        hod_name=hod.name,
        department=department,
        attendance_summary=attendance_summary,
        late_students_detail=late_students_detail,
        selected_date=selected_date,
        title="HOD Dashboard"
    )

@app.route('/calendar_view')
@login_required
def calendar_view():
    if session.get('user_type') != 'HOD':
        return redirect(url_for('index'))

    hod = HOD.query.get(current_user.id)
    if not hod:
        flash("HOD not found!", "danger")
        return redirect(url_for('index'))

    department = hod.department
    all_sections = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

    # Get attendance for a selected date
    selected_date = request.args.get('date')
    if not selected_date:
        selected_date = date.today()
    else:
        selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()

    if department == "H&S":
        # H&S-specific: department and section-wise summary
        all_departments = ['CSE', 'ECE', 'IT', 'CSE-DS', 'CSE-AIML', 'CSE-AIDS']
        attendance_summary = {dept: {section: 0 for section in all_sections} for dept in all_departments}
        present_students_detail = {dept: {section: [] for section in all_sections} for dept in all_departments}

        students = Student.query.filter_by(year=1).all()  # Fetch all 1st-year students
        for student in students:
            dept = student.department
            section = student.section
            # Check if there is no LateAttendance record for the student on the selected date
            late_record = LateAttendance.query.filter_by(student_id=student.id, date=selected_date).first()

            if not late_record:  # If no late record exists, the student is considered present
                attendance_summary[dept][section] += 1
                present_students_detail[dept][section].append({
                    'roll_no': student.roll_no,
                    'name': student.name
                })
    else:
        # Regular HOD: year and section-wise summary
        all_years = [2, 3, 4]  # Exclude 1st year for non-H&S departments
        attendance_summary = {year: {section: 0 for section in all_sections} for year in all_years}
        present_students_detail = {year: {section: [] for section in all_sections} for year in all_years}

        students = Student.query.filter_by(department=department).all()
        for student in students:
            year = student.year
            section = student.section
            # Check if there is no LateAttendance record for the student on the selected date
            late_record = LateAttendance.query.filter_by(student_id=student.id, date=selected_date).first()

            if not late_record:  # If no late record exists, the student is considered present
                attendance_summary[year][section] += 1
                present_students_detail[year][section].append({
                    'roll_no': student.roll_no,
                    'name': student.name
                })

    return render_template(
        'calendar_view.html',
        hod_name=hod.name,
        department=department,
        attendance_summary=attendance_summary,
        present_students_detail=present_students_detail,
        selected_date=selected_date
    )


@app.route('/get_late_students/<string:department_or_year>/<string:section>', methods=['GET'])
@login_required
def get_late_students(department_or_year, section):
    if session.get('user_type') != 'HOD':
        return redirect(url_for('index'))

    hod = current_user
    department = hod.department

    if department == "H&S":
        # H&S-specific: Use department as the key
        students = Student.query.filter_by(department=department_or_year, year=1, section=section).all()
    else:
        # Regular HOD: Use year as the key
        students = Student.query.filter_by(department=department, year=int(department_or_year), section=section).all()

    late_students = [
        {'roll_no': student.roll_no, 'name': student.name}
        for student in students if student.month_late_count > 0
    ]

    return jsonify(late_students)


# Principal Registration and Dashboard
@app.route('/principal_register', methods=['GET', 'POST'])
def principal_register():
    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']
        new_principal = Principal(name=name, password=password)
        db.session.add(new_principal)
        db.session.commit()
        flash('Principal registered successfully', 'success')
        return redirect(url_for('index'))
    return render_template('principal_register.html', title="Principal Register")



@app.route('/principal_dashboard', methods=['GET', 'POST'])
@login_required
def principal_dashboard():
    if session.get('user_type') != 'Principal':
        return redirect(url_for('index'))

    # Define quotes list
    principal_quotes = [
        "Education is the most powerful weapon which you can use to change the world. - Nelson Mandela",
        "Leadership is not about being in charge. It is about taking care of those in your charge. - Simon Sinek",
        "The best way to predict the future is to create it. - Peter Drucker",
        "A leader is one who knows the way, goes the way, and shows the way. - John C. Maxwell",
        "Innovation distinguishes between a leader and a follower. - Steve Jobs",
        "Do not follow where the path may lead. Go instead where there is no path and leave a trail. - Ralph Waldo Emerson",
        "Leadership is unlocking people's potential to become better. - Bill Bradley",
        "True leaders create more leaders, not followers.",
        "The function of leadership is to produce more leaders, not more followers. - Ralph Nader",
        "Leadership and learning are indispensable to each other. - John F. Kennedy"
    ]
    
    # Select a random quote
    random_quote = random.choice(principal_quotes)

    # Handling date navigation
    selected_date = request.form.get('selected_date')
    if selected_date:
        selected_date = date.fromisoformat(selected_date)
    else:
        selected_date = date.today()

    # Fetch late attendance for the selected date
    late_attendance = (
        db.session.query(Student, LateAttendance)
        .join(LateAttendance, and_(Student.id == LateAttendance.student_id, LateAttendance.date == selected_date))
        .all()
    )
  
    # Organize attendance summary by department and year
    department_summary = {}
    first_year_summary = {}

    # Explicitly add 'H&S' for first-year students
    first_year_summary['H&S'] = {'count': 0, 'departments': {}}

    # Add other departments (CSE, ECE, IT, etc.) for years 2, 3, 4
    departments = db.session.query(Student.department).distinct().all()
    for department, in departments:
        if department != 'H&S':  # Skip H&S as it's handled separately
            department_summary[department] = {
                'count': 0,
                'yearly_counts': {2: 0, 3: 0, 4: 0}  # Initialize with integer keys
            }

    # Loop through all students and update their attendance counts
    for student, _ in late_attendance:
        # Handle first year separately
        if student.year == 'H&S':  # First Year - H&S
            if student.department not in first_year_summary['H&S']['departments']:
                first_year_summary['H&S']['departments'][student.department] = 0
            first_year_summary['H&S']['departments'][student.department] += 1
        else:
            # Other years (2, 3, 4)
            try:
                year = int(student.year)  # Convert year to integer
                if year in [2, 3, 4]:  # Only process valid years
                    department_summary[student.department]['count'] += 1
                    department_summary[student.department]['yearly_counts'][year] += 1
            except (ValueError, TypeError):
                continue  # Skip invalid year values

    # Button to clear all student data
    if request.method == 'POST' and 'clear_data' in request.form:
        Student.query.delete()
        db.session.commit()
        flash('All student data has been cleared successfully.', 'success')
        return redirect(url_for('principal_dashboard'))

    return render_template(
        'principal_dashboard.html',
        department_summary=department_summary,
        first_year_summary=first_year_summary,
        selected_date=selected_date,
        random_quote=random_quote,
        title="Principal Dashboard"
    )




@app.route('/view_students')
@login_required
def view_students():
    if session.get('user_type') != 'Principal':
        return redirect(url_for('index'))
    
    # Fetch all students, including H&S (1st year) students
    students = Student.query.all()  # Fetch all students
    hs_students = Student.query.filter_by(year='H&S').all()  # Fetch only 1st-year (H&S) students

    return render_template(
        'view_students.html',
        students=students,
        hs_students=hs_students,
        title="All Students"
    )


@app.route('/view_roles')
@login_required
def view_roles():
    if session.get('user_type') != 'Principal':
        return redirect(url_for('index'))
    
    faculty = Faculty.query.all()  # Fetch all faculty details
    discipline_incharge = DisciplineIncharge.query.all()  # Fetch discipline in charge details
    hods = HOD.query.all()  # Fetch HOD details, including H&S HOD
    hs_hod = HOD.query.filter_by(department='H&S').first()  # Fetch the H&S HOD separately

    return render_template(
        'view_roles.html',
        faculty=faculty,
        discipline_incharge=discipline_incharge,
        hods=hods,
        hs_hod=hs_hod,
        title="Registered Roles"
    )

# Routes to delete a specific Faculty, Discipline Incharge, or HOD
@app.route('/delete_faculty/<int:id>', methods=['POST'])
@login_required
def delete_faculty(id):
    if session.get('user_type') != 'Principal':
        return redirect(url_for('index'))

    faculty = Faculty.query.get(id)
    if faculty:
        db.session.delete(faculty)
        db.session.commit()
        flash('Faculty member deleted successfully.', 'success')
    else:
        flash('Faculty member not found.', 'danger')
    return redirect(url_for('view_roles'))

@app.route('/delete_discipline_incharge/<int:id>', methods=['POST'])
@login_required
def delete_discipline_incharge(id):
    if session.get('user_type') != 'Principal':
        return redirect(url_for('index'))

    incharge = DisciplineIncharge.query.get(id)
    if incharge:
        db.session.delete(incharge)
        db.session.commit()
        flash('Discipline Incharge deleted successfully.', 'success')
    else:
        flash('Discipline Incharge not found.', 'danger')
    return redirect(url_for('view_roles'))

@app.route('/delete_hod/<int:id>', methods=['POST'])
@login_required
def delete_hod(id):
    if session.get('user_type') != 'Principal':
        return redirect(url_for('index'))

    hod = HOD.query.get(id)
    if hod:
        db.session.delete(hod)
        db.session.commit()
        flash('HOD deleted successfully.', 'success')
    else:
        flash('HOD not found.', 'danger')
    return redirect(url_for('view_roles'))

def load_students_from_csv(file_path):
    print(f"Loading students from: {file_path}")
    
    if not os.path.exists(file_path):
        flash('File not found. Please upload a valid CSV file.', 'danger')
        return
    
    try:
        with open(file_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            
            # Define expected headers from the CSV
            expected_headers = {'name', 'roll_no', 'year', 'department', 'section', 'parent_email', 'parent_mobile'}
            if not expected_headers.issubset(reader.fieldnames):
                flash('CSV headers do not match the expected format.', 'danger')
                return
            
            students = []
            for row in reader:
                print(f"Processing row: {row}")
                # Clean and standardize roll number
                roll_no = row['roll_no'].strip().upper()  # Convert to uppercase and remove spaces
                
                # Check if student already exists
                existing_student = Student.query.filter_by(roll_no=roll_no).first()
                if existing_student:
                    print(f"Student with roll number {roll_no} already exists. Skipping.")
                    continue
                
                # Prepare data for insertion using SQLAlchemy
                student = Student(
                    name=row['name'].strip(),
                    roll_no=roll_no,
                    year=row['year'].strip(),
                    department=row['department'].strip(),
                    section=row['section'].strip(),
                    parent_email=row['parent_email'].strip(),
                    parent_mobile=row['parent_mobile'].strip(),
                    late_count=0,
                    week_late_count=0,
                    month_late_count=0
                )
                students.append(student)
                print(f"Added student: {student.name} (Roll No: {student.roll_no})")

            if students:
                db.session.add_all(students)  # Add all student objects to the session
                db.session.commit()  # Commit to save to the database
                flash(f'Successfully loaded {len(students)} students from CSV.', 'success')
            else:
                flash('No new students found in CSV.', 'warning')
    
    except Exception as e:
        print(f"Error: {e}")
        db.session.rollback()  # Rollback in case of error
        flash(f'Failed to load students. Error: {e}', 'danger')
        
@app.route('/load_students', methods=['GET', 'POST'])
def load_students():
    form = UploadForm()
    if form.validate_on_submit():
        file = form.file.data
        if file and file.filename.endswith('.csv'):
            # Save the file to the uploads folder
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)
            
            # Call the function to load students from CSV
            load_students_from_csv(file_path)

            # Flash success message and redirect to view students page
            flash('Students loaded successfully from CSV', 'success')
            return redirect(url_for('view_students'))
        else:
            flash('Invalid file type. Please upload a CSV file.', 'danger')
    
    # Render the load students page for GET requests
    return render_template('load_students.html', title="Load Students", form=form)

@app.route('/clear_students', methods=['POST'])
def clear_students():
    try:
        # First delete all late attendance records
        LateAttendance.query.delete()
        # Then delete all students
        Student.query.delete()
        db.session.commit()
        flash('All student data has been cleared successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error clearing data: {str(e)}', 'danger')
    return redirect(url_for('load_students'))

# Notification functions
def send_email_notification(parent_email, student_name):
    sender_email = "your_email@example.com"
    sender_password = "your_email_password"
    subject = "Late Attendance Alert"
    body = f"Your child, {student_name}, has been marked late."

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = parent_email

    try:
        with smtplib.SMTP_SSL('smtp.example.com', 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
    except Exception as e:
        print(f"Failed to send email: {e}")

def send_sms_notification(parent_mobile, student_name):
    # Add your SMS API logic here
    print(f"Sending SMS to {parent_mobile}: {student_name} has been marked late.")

if __name__ == '__main__':
    app.run(debug=True)
