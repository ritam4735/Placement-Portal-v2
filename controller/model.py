from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

database = SQLAlchemy()

# -------------------------
# STUDENT
# -------------------------
class Student(database.Model):
    __tablename__ = "students"

    id = database.Column(database.Integer, primary_key=True)
    name = database.Column(database.String(120), nullable=False)
    email = database.Column(database.String(120), unique=True, nullable=False)
    age = database.Column(database.Integer)
    gender = database.Column(database.String(20))
    phone = database.Column(database.String(20))
    password = database.Column(database.String(255), nullable=False)
    
    # pending / approved / blocked / rejected
    status = database.Column(database.String(50), default="pending")
    created_at = database.Column(database.DateTime, default=datetime.utcnow)

    # Eligibility criteria
    cgpa = database.Column(database.Float, nullable=True)
    branch = database.Column(database.String(100), nullable=True)
    passing_year = database.Column(database.Integer, nullable=True)

# -------------------------
# COMPANY
# -------------------------
class Company(database.Model):
    __tablename__ = "companies"

    id = database.Column(database.Integer, primary_key=True)
    company_name = database.Column(database.String(200), nullable=False)
    email = database.Column(database.String(120), unique=True, nullable=False)
    phone = database.Column(database.String(20))
    website = database.Column(database.String(200))
    password = database.Column(database.String(255), nullable=False)
    
    # pending / approved / blocked / rejected
    status = database.Column(database.String(50), default="pending")
    created_at = database.Column(database.DateTime, default=datetime.utcnow)

# -------------------------
# EMPLOYEE / ADMIN
# -------------------------
class Employee(database.Model):
    __tablename__ = "employees"

    id = database.Column(database.Integer, primary_key=True)
    username = database.Column(database.String(120), unique=True, nullable=False)
    password = database.Column(database.String(255), nullable=False)
    
    # admin / staff
    role = database.Column(database.String(50), default="staff")
    # full / manage_students / manage_companies / manage_jobs / viewer
    power = database.Column(database.String(50), default="none")
    # pending / approved / blocked
    status = database.Column(database.String(50), default="pending")
    created_at = database.Column(database.DateTime, default=datetime.utcnow)

# -------------------------
# PLACEMENT DRIVE / JOB
# -------------------------
class Job(database.Model):
    __tablename__ = "jobs"

    id = database.Column(database.Integer, primary_key=True)
    title = database.Column(database.String(200), nullable=False)
    description = database.Column(database.Text, nullable=False)
    company_id = database.Column(database.Integer, nullable=False)

    # Optional eligibility fields
    branch = database.Column(database.String(100))
    cgpa = database.Column(database.Float)
    year = database.Column(database.Integer)
    application_deadline = database.Column(database.DateTime)

    # pending / approved / closed / rejected
    status = database.Column(database.String(50), default="pending")
    created_at = database.Column(database.DateTime, default=datetime.utcnow)

# -------------------------
# JOB APPLICATION
# -------------------------
class Application(database.Model):
    __tablename__ = "applications"

    id = database.Column(database.Integer, primary_key=True)
    job_id = database.Column(database.Integer, nullable=False)
    student_id = database.Column(database.Integer, nullable=False)
    education = database.Column(database.String(200), nullable=False)
    cv_file = database.Column(database.String(300), nullable=False)

    # applied / shortlisted / selected / rejected / withdrawn
    status = database.Column(database.String(50), default="applied")
    applied_at = database.Column(database.DateTime, default=datetime.utcnow)

# -------------------------
# NOTIFICATIONS
# -------------------------
class Notification(database.Model):
    __tablename__ = "notifications" 

    id = database.Column(database.Integer, primary_key=True)
    user_role = database.Column(database.String(50))
    user_id = database.Column(database.Integer)
    message = database.Column(database.String(500))
    is_read = database.Column(database.Boolean, default=False)
    created_at = database.Column(database.DateTime, default=datetime.utcnow)

# -------------------------
# INTERVIEW
# -------------------------
class Interview(database.Model):
    __tablename__ = "interviews" 

    id = database.Column(database.Integer, primary_key=True)
    application_id = database.Column(database.Integer)
    date = database.Column(database.String(50))
    time = database.Column(database.String(50))
    location = database.Column(database.String(200))