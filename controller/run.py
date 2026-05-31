import uuid
import csv
from pathlib import Path
from datetime import datetime, timedelta, timezone 
import jwt

from flask import Flask, jsonify, render_template, request, session, redirect, send_from_directory
from flask_caching import Cache
from celery import Celery
from werkzeug.utils import secure_filename
from sqlalchemy import text

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import timedelta
from celery.schedules import crontab

# import your models
from model import database, Student, Company, Employee, Job, Application, Notification, Interview

JWT_SECRET = "secret-key" 
JWT_ALGORITHM = "HS256"

# ---------------- PATHS ----------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"
INSTANCE_DIR = PROJECT_ROOT / "instance"
UPLOAD_DIR = PROJECT_ROOT / "uploads"

DATABASE_PATH = INSTANCE_DIR / "users.db"

UPLOAD_DIR.mkdir(exist_ok=True)
INSTANCE_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}

# ---------------- CACHE ----------------
cache = Cache(config={
    "CACHE_TYPE": "RedisCache",
    "CACHE_REDIS_URL": "redis://localhost:6379/0"
})


# ---------------- CELERY ----------------
def make_celery(app):
    celery = Celery(
        app.import_name,
        # Using 127.0.0.1 is more stable than 'localhost' on Windows
        broker="redis://127.0.0.1:6379/0",
        backend="redis://127.0.0.1:6379/0"
    )
    celery.conf.update(app.config)
    
    # ADD THIS LINE: This fixes the "not enough values to unpack" error on Windows
    celery.conf.worker_pool = 'solo'
    
    return celery

# ---------------- EMAIL SETUP ----------------
SMTP_SERVER = "localhost"
SMTP_PORT = 1025 # Default port for MailHog
MAIL_USE_TLS = False
MAIL_USE_SSL = False
MAIL_USERNAME = None
MAIL_PASSWORD = None
SENDER_EMAIL = "noreply@pl.local"

def send_email(to_email, subject, html_body):
    try:
        msg = MIMEMultipart("alternative")
        msg['Subject'] = subject
        msg['From'] = SENDER_EMAIL
        msg['To'] = to_email
        msg.attach(MIMEText(html_body, "html"))
        
        # Added timeout=5 to prevent hanging if Mailpit is closed
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=5) as server:
            server.send_message(msg)
            print(f"Successfully sent email to {to_email} via Mailpit")
            
    except Exception as e:
        # This will now show you the ACTUAL error if it still fails
        print(f"!!! SMTP Connection Error: {e}")
        print(f"[EMAIL SIMULATION to {to_email}] {subject}\n{html_body}\n")

# ---------------- HELPERS / MIGRATION ----------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_jwt(user_id, role):
    try:
        payload = {
            # exp: expiration time (1 day from now)
            'exp': datetime.now(timezone.utc) + timedelta(days=1),
            # iat: issued at time
            'iat': datetime.now(timezone.utc),
            # sub: the user identifier (converted to string for safety)
            'sub': str(user_id),
            'role': role
        }
        # Generate the token string
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        return token
    except Exception as e:
        print(f"!!! JWT Generation Error: {e}")
        return None

def decode_jwt(token):
    try:
        # returns the dictionary payload if valid
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return {"error": "Token expired"}
    except jwt.InvalidTokenError:
        return {"error": "Invalid token"}
def create_notification(role, uid, message):
    try:
        n = Notification(user_role=role, user_id=uid, message=message)
        database.session.add(n)
        database.session.commit()
    except Exception as e:
        app.logger.debug("create_notification error (ignored): %s", e)

def _table_has_column(table: str, column: str) -> bool:
    try:
        q = database.session.execute(text(f"PRAGMA table_info('{table}')"))
        cols = [r[1] for r in q.fetchall()]
        return column in cols
    except Exception as e:
        app.logger.debug("PRAGMA table_info error for %s: %s", table, e)
        return False

def migrate_tables():
    """Add missing columns to existing SQLite tables."""
    conn = database.engine.connect()
    try:
        if not _table_has_column("employees", "created_at"):
            try: conn.execute(text("ALTER TABLE employees ADD COLUMN created_at DATETIME DEFAULT (datetime('now'))"))
            except Exception: pass
        if not _table_has_column("students", "created_at"):
            try: conn.execute(text("ALTER TABLE students ADD COLUMN created_at DATETIME DEFAULT (datetime('now'))"))
            except Exception: pass
        if not _table_has_column("companies", "created_at"):
            try: conn.execute(text("ALTER TABLE companies ADD COLUMN created_at DATETIME DEFAULT (datetime('now'))"))
            except Exception: pass
        if not _table_has_column("jobs", "created_at"):
            try: conn.execute(text("ALTER TABLE jobs ADD COLUMN created_at DATETIME DEFAULT (datetime('now'))"))
            except Exception: pass
        if not _table_has_column("applications", "applied_at"):
            try: conn.execute(text("ALTER TABLE applications ADD COLUMN applied_at DATETIME DEFAULT (datetime('now'))"))
            except Exception: pass
        if not _table_has_column("applications", "status"):
            try: conn.execute(text("ALTER TABLE applications ADD COLUMN status TEXT DEFAULT 'applied'"))
            except Exception: pass
        if _table_has_column("notifications", "id"):
            if not _table_has_column("notifications", "is_read"):
                try: conn.execute(text("ALTER TABLE notifications ADD COLUMN is_read INTEGER DEFAULT 0"))
                except Exception: pass
            if not _table_has_column("notifications", "created_at"):
                try: conn.execute(text("ALTER TABLE notifications ADD COLUMN created_at DATETIME DEFAULT (datetime('now'))"))
                except Exception: pass
        if _table_has_column("interviews", "id"):
            if not _table_has_column("interviews", "created_at"):
                try: conn.execute(text("ALTER TABLE interviews ADD COLUMN created_at DATETIME DEFAULT (datetime('now'))"))
                except Exception: pass
    finally:
        conn.close()

# ---------------- CREATE APP ----------------
def create_app():
    global app
    app = Flask(
        __name__,
        template_folder=str(TEMPLATES_DIR),
        static_folder=str(STATIC_DIR),
        instance_path=str(INSTANCE_DIR)
    )

    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DATABASE_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "secret-key"

    database.init_app(app)
    cache.init_app(app)

    with app.app_context():
        database.create_all()
        try:
            migrate_tables()
        except Exception as e:
            app.logger.debug("Migration step failed: %s", e)

        try:
            admin = Employee.query.filter_by(username="admin").first()
            if not admin:
                admin = Employee(
                    username="admin",
                    password="admin123",
                    role="admin",
                    power="full",
                    status="approved",
                    created_at=datetime.utcnow() if hasattr(Employee, "created_at") else None
                )
                database.session.add(admin)
                database.session.commit()
        except Exception as e:
            app.logger.debug("Admin creation/query error: %s", e)

    return app

app = create_app()
celery = make_celery(app)

# ---------------- CELERY BEAT SCHEDULE ----------------
celery.conf.beat_schedule = {
    'daily-deadline-reminders': {
        'task': 'run.send_daily_reminders',
        # TESTING MODE: Runs every 1 minute!
        'schedule': crontab(minute='*'), 
    },
    'monthly-admin-report': {
        'task': 'run.send_monthly_report',
        # TESTING MODE: Runs every 1 minute!
        'schedule': crontab(minute='*'), 
    }
}
celery.conf.timezone = 'Asia/Kolkata'

# ---------------- CELERY TASKS ----------------

@celery.task(name='run.notify_admin')
def notify_admin(role, email):
    print(f"[celery] notify_admin: new {role} -> {email}")

@celery.task(name='run.notify_company')
def notify_company(job_id):
    print(f"[celery] notify_company: new application for job {job_id}")

@celery.task(name='run.export_applications_csv')
def export_applications_csv(student_id):
    with app.app_context():
        apps = Application.query.filter_by(student_id=student_id).all()
        
        # Create a unique filename
        filename = f"export_student_{student_id}_{uuid.uuid4().hex[:8]}.csv"
        filepath = UPLOAD_DIR / filename
        
        # Write data to the CSV file
        with open(filepath, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Student ID', 'Company Name', 'Drive Title', 'Application Status', 'Application Date'])
            
            for a in apps:
                job = Job.query.get(a.job_id)
                comp = Company.query.get(job.company_id) if job else None
                comp_name = comp.company_name if comp else "N/A"
                job_title = job.title if job else "N/A"
                app_date = a.applied_at.strftime('%Y-%m-%d %H:%M:%S') if getattr(a, 'applied_at', None) else "N/A"
                
                writer.writerow([student_id, comp_name, job_title, a.status, app_date])
        
        # Send a notification to the student with a download link!
        msg = f"Your CSV export is ready! <a href='/uploads/{filename}' target='_blank' style='color:#93c5fd; text-decoration:underline;'>Download Here</a>"
        create_notification("student", student_id, msg)
        
        return filename
    
@celery.task(name='run.send_daily_reminders')
def send_daily_reminders():
    with app.app_context():
        tomorrow = datetime.utcnow() + timedelta(days=1)
        active_jobs = Job.query.filter_by(status="approved").all()
        students = Student.query.filter_by(status="approved").all()
        
        reminders_sent = 0
        
        for job in active_jobs:
            if job.application_deadline and job.application_deadline.date() == tomorrow.date():
                applied_ids = [a.student_id for a in Application.query.filter_by(job_id=job.id).all()]
                
                for student in students:
                    if student.id not in applied_ids:
                        html_content = f"<h3>Reminder!</h3><p>Hi {student.name}, the deadline to apply for <b>{job.title}</b> is tomorrow! Don't miss out.</p>"
                        
                
                        student_email = student.email if student.email and "@" in student.email else f"student_{student.id}@placementportal.com"
                        
                        send_email(student_email, f"Deadline Approaching: {job.title}", html_content)
                        create_notification("student", student.id, f"Reminder: Deadline for {job.title} is tomorrow!")
                        reminders_sent += 1
                        
        # Notify the Admin in the frontend that the batch job ran
        admin = Employee.query.filter_by(role="admin").first()
        if admin:
            create_notification("employee", admin.id, f"System Update: Daily batch job sent {reminders_sent} reminder(s) to students.")
            
        return "Daily reminders processed."

@celery.task(name='run.send_monthly_report')
def send_monthly_report():
    with app.app_context():
        admin = Employee.query.filter_by(role="admin").first()
        if not admin:
            return "No admin found."
            
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        new_drives = Job.query.filter(Job.created_at >= thirty_days_ago).count()
        total_applications = Application.query.filter(Application.applied_at >= thirty_days_ago).count()
        students_hired = Application.query.filter(Application.status == "selected", Application.applied_at >= thirty_days_ago).count()
        
        html_report = render_template("monthly_report.html", 
                                      drives=new_drives, 
                                      applications=total_applications, 
                                      hired=students_hired,
                                      month=datetime.utcnow().strftime("%B %Y"))
        
        # Generic email format (No IITM)
        admin_email = admin.username if "@" in admin.username else "admin@placementportal.com"
                                      
        send_email(admin_email, "Monthly Placement Activity Report", html_report)
        
        # Show a notification in the Admin's frontend bell!
        create_notification("employee", admin.id, f"The Monthly Report for {datetime.utcnow().strftime('%B %Y')} has been generated and emailed.")
        
        return "Monthly report sent to Admin."


# ---------------- PAGES & API ENDPOINTS ----------------
@app.get("/")
def index():
    return render_template("login.html")

@app.get("/home")
def home():
    role = session.get("role")
    uid = session.get("user_id")

    if not role:
        return redirect("/")

    if role == "student":
        user = Student.query.get(uid)
        name = user.name
    elif role == "company":
        user = Company.query.get(uid)
        name = user.company_name
    else:
        user = Employee.query.get(uid)
        name = user.username

    try:
        notifications = Notification.query.filter_by(
            user_role=role,
            user_id=uid
        ).order_by(Notification.created_at.desc()).all()
    except:
        notifications = []

    return render_template(
        "home.html",
        role=role,
        name=name,
        notifications=notifications
    )

@app.get("/api/me")
def get_me():
    role = session.get("role")
    uid = session.get("user_id")
    
    if not role or not uid:
        return jsonify({"message": "Unauthorized"}), 401

    if role == "student":
        user = Student.query.get(uid)
        return jsonify({
            "name": user.name, 
            "power": "none",
            "cgpa": user.cgpa,
            "branch": user.branch,
            "passing_year": user.passing_year
        }) if user else (jsonify({}), 404)
    elif role == "company":
        user = Company.query.get(uid)
        return jsonify({"name": user.company_name, "power": "none"}) if user else (jsonify({}), 404)
    else:
        user = Employee.query.get(uid)
        if user:
            return jsonify({"name": user.username, "power": getattr(user, 'power', 'full')})
        return jsonify({}), 404

@app.post("/api/update_profile")
def update_profile():
    if session.get("role") != "student":
        return jsonify({"message": "Unauthorized"}), 403
        
    data = request.get_json() or {}
    student = Student.query.get(session.get("user_id"))
    
    if not student:
        return jsonify({"message": "Student not found"}), 404
        
    student.cgpa = float(data.get("cgpa")) if data.get("cgpa") else None
    student.branch = data.get("branch")
    student.passing_year = int(data.get("passing_year")) if data.get("passing_year") else None
    
    database.session.commit()
    return jsonify({"message": "Profile updated successfully!"}), 200

@app.post("/api/register")
def register():  # Notice: No 'async' and no '{'
    data = request.get_json() or {}
    role = data.get("role")
    email = data.get("email")

    # Check if user already exists
    if role == "student":
        existing = Student.query.filter_by(email=email).first()
    elif role == "company":
        existing = Company.query.filter_by(email=email).first()
    else:
        existing = Employee.query.filter_by(username=email).first()

    if existing:
        return jsonify({"message": "Email already registered!"}), 400

    try:
        if role == "student":
            user = Student(
                name=data.get("name"), email=email, age=data.get("age"),
                gender=data.get("gender"), phone=data.get("phone"),
                password=data.get("password"), status="pending"
            )
        elif role == "company":
            user = Company(
                company_name=data.get("company_name"), email=email,
                phone=data.get("phone"), password=data.get("password"), status="pending"
            )
        else:
            user = Employee(
                username=email, password=data.get("password"),
                role="staff", power="none", status="pending"
            )

        database.session.add(user)
        database.session.commit()
        return jsonify({"message": "Registration submitted successfully!"}), 201
    except Exception as e:
        database.session.rollback()
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    
    
@app.post("/api/login")
def login():
    data = request.get_json() or {}
    role = data.get("role")
    email = data.get("email")
    password = data.get("password")
    
    if role == "student":
        user = Student.query.filter_by(email=email).first()
    elif role == "company":
        user = Company.query.filter_by(email=email).first()
    else:
        user = Employee.query.filter_by(username=email).first()
        
    if not user or user.password != password:
        return jsonify({"message": "Invalid credentials"}), 401
    if user.status != "approved":
        return jsonify({"message": "Account not approved"}), 403
        
    # 1. Keep your existing session logic if you still want it
    session["role"] = role
    session["user_id"] = user.id

    # 2. GENERATE THE JWT TOKEN
    token = generate_jwt(user.id, role)

    # 3. Return the token to the frontend
    return jsonify({
        "message": "Login successful",
        "token": token,  # The frontend should save this in localStorage
        "redirect": "/home"
    }), 200

@app.get("/api/students")
@cache.cached(timeout=30)
def get_students():
    students = Student.query.filter_by(status="pending").all()
    return jsonify([{"id": s.id, "name": s.name, "email": s.email, "status": s.status} for s in students])

@app.get("/api/companies")
@cache.cached(timeout=30)
def get_companies():
    companies = Company.query.filter_by(status="pending").all()
    return jsonify([{"id": c.id, "name": c.company_name, "email": c.email, "status": c.status} for c in companies])

@app.get("/api/employees")
def get_employees():
    employees = Employee.query.filter_by(status="pending").all()
    return jsonify([{"id": e.id, "username": e.username, "power": e.power, "status": e.status} for e in employees])

# NEW: Fetch Approved Employees
@app.get("/api/employees_approved")
def employees_approved():
    employees = Employee.query.filter_by(status="approved").all()
    return jsonify([{"id": e.id, "username": e.username, "power": e.power, "status": e.status} for e in employees])

# NEW: Update Employee Power
@app.post("/api/update_employee_power")
def update_employee_power():
    data = request.get_json() or {}
    emp_id = data.get("id")
    new_power = data.get("power")
    
    emp = Employee.query.get(emp_id)
    if not emp: return jsonify({"message": "Employee not found"}), 404
    
    emp.power = new_power
    database.session.commit()
    return jsonify({"message": "Power updated successfully"})

@app.post("/api/approve_user")
def approve_user():
    data = request.get_json() or {}
    role = data.get("role")
    uid = data.get("id")
    
    if role == "student":
        user = Student.query.get(uid)
    elif role == "company":
        user = Company.query.get(uid)
    else:
        user = Employee.query.get(uid)
        
    if not user:
        return jsonify({"message": "User not found"}), 404
        
    user.status = "approved"
    database.session.commit()
    cache.clear() 
    
    try:
        create_notification(role, uid, "Your account has been approved")
    except Exception:
        pass
    return jsonify({"message": "User approved"})

@app.post("/api/reject_user")
def reject_user():
    data = request.get_json() or {}
    role = data.get("role")
    uid = data.get("id")
    
    if role == "student":
        user = Student.query.get(uid)
    elif role == "company":
        user = Company.query.get(uid)
    else:
        user = Employee.query.get(uid)
        
    if not user:
        return jsonify({"message": "User not found"}), 404
        
    user.status = "rejected"
    database.session.commit()
    cache.clear()
    
    try:
        create_notification(role, uid, "Your account registration was rejected")
    except Exception:
        pass
    return jsonify({"message": "User rejected"})

@app.get("/api/students_approved")
@cache.cached(timeout=30)
def students_approved():
    students = Student.query.filter(Student.status.in_(["approved", "blocked"])).all()
    return jsonify([{"id": s.id, "name": s.name, "email": s.email, "status": s.status} for s in students])

@app.get("/api/companies_approved")
@cache.cached(timeout=30)
def companies_approved():
    companies = Company.query.filter(Company.status.in_(["approved", "blocked"])).all()
    return jsonify([{"id": c.id, "name": c.company_name, "email": c.email, "status": c.status} for c in companies])

@app.post("/api/block_user")
def block_user():
    data = request.get_json() or {}
    role = data.get("role")
    uid = data.get("id")
    
    if role == "student":
        user = Student.query.get(uid)
    elif role == "company":
        user = Company.query.get(uid)
    else:
        return jsonify({"message": "Invalid role"}), 400
        
    if not user:
        return jsonify({"message": "User not found"}), 404
        
    user.status = "blocked"
    database.session.commit()
    cache.clear()
    return jsonify({"message": "User blocked"})

@app.post("/api/unblock_user")
def unblock_user():
    data = request.get_json() or {}
    role = data.get("role")
    uid = data.get("id")

    if role == "student":
        user = Student.query.get(uid)
    elif role == "company":
        user = Company.query.get(uid)
    else:
        return jsonify({"message": "Invalid role"}), 400

    if not user:
        return jsonify({"message": "User not found"}), 404

    user.status = "approved"
    database.session.commit()
    cache.clear()
    return jsonify({"message": "User unblocked"})

@app.post("/api/delete_user")
def delete_user():
    data = request.get_json() or {}
    role = data.get("role")
    uid = data.get("id")
    
    if role == "student": user = Student.query.get(uid)
    elif role == "company": user = Company.query.get(uid)
    elif role == "employee": user = Employee.query.get(uid)
    else: return jsonify({"message": "Invalid role"}), 400
        
    if not user:
        return jsonify({"message": "User not found"}), 404
        
    database.session.delete(user)
    database.session.commit()
    cache.clear()
    return jsonify({"message": "User deleted"})

@app.get("/api/search_students")
def search_students():
    q = request.args.get("q", "")
    students = Student.query.filter(Student.name.contains(q)).all()
    return jsonify([{"id": s.id, "name": s.name, "email": s.email} for s in students])

@app.get("/api/search_companies")
def search_companies():
    q = request.args.get("q", "")
    comps = Company.query.filter(Company.company_name.contains(q)).all()
    return jsonify([{"id": c.id, "name": c.company_name, "email": c.email} for c in comps])

@app.get("/api/notifications")
def notifications():
    role = session.get("role")
    uid = session.get("user_id")
    try:
        notes = Notification.query.filter_by(user_role=role, user_id=uid).order_by(Notification.created_at.desc()).all()
        return jsonify([{"id": n.id, "message": n.message, "read": getattr(n, "is_read", False)} for n in notes])
    except Exception:
        return jsonify([])

@app.post("/api/read_notification")
def read_notification():
    data = request.get_json() or {}
    nid = data.get("id")
    try:
        n = Notification.query.get(nid)
        if not n:
            return jsonify({"message": "Notification not found"}), 404
        n.is_read = True
        database.session.commit()
        return jsonify({"message": "Notification marked read"})
    except Exception:
        return jsonify({"message":"failed"}), 500

@app.post("/api/post_job")
def post_job():
    data = request.get_json() or {}
    
    deadline_str = data.get("deadline")
    deadline_dt = None
    if deadline_str:
        try:
            deadline_dt = datetime.strptime(deadline_str, "%Y-%m-%d")
        except:
            pass

    job = Job(
        title=data.get("title"),
        description=data.get("description"),
        company_id=session.get("user_id"),
        branch=data.get("branch"),
        cgpa=float(data.get("cgpa")) if data.get("cgpa") else None,
        year=int(data.get("year")) if data.get("year") else None,
        application_deadline=deadline_dt,
        status="pending"
    )
    database.session.add(job)
    database.session.commit()
    
    try:
        notify_admin.delay("job", job.id)
    except Exception:
        pass
    return jsonify({"message": "Job submitted for admin approval"}), 201

@app.get("/api/company_jobs")
def company_jobs():
    cid = session.get("user_id")
    jobs = Job.query.filter_by(company_id=cid).all()
    return jsonify([{"id": j.id, "title": j.title, "description": j.description, "status": j.status} for j in jobs])

@app.post("/api/update_job")
def update_job():
    data = request.get_json() or {}
    job = Job.query.get(data.get("id"))
    
    if not job:
        return jsonify({"message": "Job not found"}), 404
    if job.company_id != session.get("user_id") and session.get("role") != "employee":
        return jsonify({"message": "Unauthorized"}), 403
        
    job.title = data.get("title")
    job.description = data.get("description")
    database.session.commit()
    cache.clear()
    return jsonify({"message": "Job updated"})

@app.post("/api/delete_job")
def delete_job():
    data = request.get_json() or {}
    job = Job.query.get(data.get("id"))
    
    if not job:
        return jsonify({"message": "Job not found"}), 404
    if job.company_id != session.get("user_id") and session.get("role") != "employee":
        return jsonify({"message": "Unauthorized"}), 403
        
    database.session.delete(job)
    database.session.commit()
    cache.clear()
    return jsonify({"message": "Job deleted"})

@app.get("/api/pending_jobs")
def pending_jobs():
    jobs = Job.query.filter_by(status="pending").all()
    data = []
    for j in jobs:
        company = Company.query.get(j.company_id)
        data.append({"id": j.id, "title": j.title, "description": j.description, "company": company.company_name if company else "—"})
    return jsonify(data)

@app.post("/api/approve_job")
def approve_job():
    data = request.get_json() or {}
    job = Job.query.get(data.get("id"))
    
    if not job:
        return jsonify({"message": "Job not found"}), 404
        
    job.status = "approved"
    database.session.commit()
    cache.clear()
    
    try:
        create_notification("company", job.company_id, f"Your job '{job.title}' was approved")
    except Exception:
        pass
    return jsonify({"message": "Job approved"})

@app.post("/api/reject_job")
def reject_job():
    data = request.get_json() or {}
    job = Job.query.get(data.get("id"))
    
    if not job:
        return jsonify({"message": "Job not found"}), 404
        
    job.status = "rejected"
    database.session.commit()
    
    try:
        create_notification("company", job.company_id, f"Your job '{job.title}' was rejected")
    except Exception:
        pass
    return jsonify({"message": "Job rejected"})

@app.get("/api/jobs")
@cache.cached(timeout=60)
def jobs():
    jobs = Job.query.filter_by(status="approved").all()
    data = []
    for j in jobs:
        company = Company.query.get(j.company_id)
        data.append({"id": j.id, "title": j.title, "description": j.description, "company": company.company_name if company else "—"})
    return jsonify(data)

@app.post("/api/apply_job")
def apply_job():
    job_id = request.form.get("job_id")
    education = request.form.get("education")
    file = request.files.get("cv")
    student_id = session.get("user_id")
    
    if not job_id or not education:
        return jsonify({"message": "Job and education are required"}), 400
    if not file:
        return jsonify({"message": "CV required"}), 400
    if not allowed_file(file.filename):
        return jsonify({"message": "Invalid file type"}), 400
        
    student = Student.query.get(student_id)
    job = Job.query.get(job_id)
    
    if not student or not job:
        return jsonify({"message": "Student or Job not found"}), 404

    existing_app = Application.query.filter_by(student_id=student_id, job_id=job_id).first()
    if existing_app and existing_app.status != "withdrawn":
        return jsonify({"message": "You have already applied for this job."}), 400

    if job.cgpa and (student.cgpa is None or student.cgpa < job.cgpa):
        return jsonify({"message": f"Required CGPA is {job.cgpa}, but your profile shows {student.cgpa or 'Nothing'}. Please update your profile."}), 403
        
    if job.branch and (student.branch is None or job.branch.lower() != student.branch.lower()):
        return jsonify({"message": f"This job requires a {job.branch} background. Your profile shows {student.branch or 'Nothing'}."}), 403
        
    if job.year and (student.passing_year is None or student.passing_year != job.year):
        return jsonify({"message": f"This job is strictly for the {job.year} batch."}), 403

    filename = secure_filename(file.filename)
    unique = f"{uuid.uuid4()}_{filename}"
    file.save(UPLOAD_DIR / unique)
    
    application = Application(
        job_id=int(job_id),
        student_id=student_id,
        education=education,
        cv_file=unique,
        status="applied"
    )
    database.session.add(application)
    database.session.commit()
    
    try:
        notify_company.delay(job_id)
    except Exception:
        pass
        
    try:
        create_notification("company", job.company_id, f"New application for '{job.title}'")
    except Exception:
        pass
        
    return jsonify({"message": "Application submitted successfully!"}), 201

@app.get("/api/my_applications")
def my_applications():
    sid = session.get("user_id")
    apps = Application.query.filter_by(student_id=sid).all()
    data = []
    for a in apps:
        job = Job.query.get(a.job_id)
        
        interview = Interview.query.filter_by(application_id=a.id).first()
        interview_data = None
        if interview:
            interview_data = {
                "date": interview.date,
                "time": interview.time,
                "location": interview.location
            }
            
        data.append({
            "id": a.id, 
            "job_id": a.job_id, 
            "job_title": job.title if job else "—", 
            "status": a.status,
            "interview": interview_data 
        })
    return jsonify(data)

@app.post("/api/withdraw_application")
def withdraw_application():
    data = request.get_json() or {}
    app_obj = Application.query.get(data.get("id"))
    
    if not app_obj:
        return jsonify({"message": "Application not found"}), 404
    if app_obj.student_id != session.get("user_id") and session.get("role") != "employee":
        return jsonify({"message": "Unauthorized"}), 403
        
    app_obj.status = "withdrawn"
    database.session.commit()
    return jsonify({"message": "Application withdrawn"})

@app.get("/api/job_applicants")
def job_applicants():
    job_id = request.args.get("job_id")
    apps = Application.query.filter_by(job_id=job_id).all()
    data = []
    for a in apps:
        student = Student.query.get(a.student_id)
        data.append({"id": a.id, "name": student.name if student else "—", "education": a.education, "cv": a.cv_file, "status": a.status})
    return jsonify(data)

@app.post("/api/approve_application")
def approve_application():
    data = request.get_json() or {}
    app_obj = Application.query.get(data.get("id"))
    
    if not app_obj:
        return jsonify({"message": "Application not found"}), 404
        
    app_obj.status = "shortlisted"
    database.session.commit()
    
    try:
        create_notification("student", app_obj.student_id, "You have been shortlisted")
    except Exception:
        pass
    return jsonify({"message": "Applicant shortlisted"})

@app.post("/api/reject_application")
def reject_application():
    data = request.get_json() or {}
    app_obj = Application.query.get(data.get("id"))
    
    if not app_obj:
        return jsonify({"message": "Application not found"}), 404
        
    app_obj.status = "rejected"
    database.session.commit()
    
    try:
        create_notification("student", app_obj.student_id, "Your application was rejected")
    except Exception:
        pass
    return jsonify({"message": "Applicant rejected"})

@app.post("/api/schedule_interview")
def schedule_interview():
    data = request.get_json() or {}
    i = Interview(
        application_id=data.get("application_id"),
        date=data.get("date"),
        time=data.get("time"),
        location=data.get("location")
    )
    database.session.add(i)
    
    app_obj = Application.query.get(data.get("application_id"))
    if app_obj:
        app_obj.status = "interview"
        
    database.session.commit()
    
    try:
        if app_obj:
            create_notification("student", app_obj.student_id, f"Interview scheduled on {i.date} {i.time} at {i.location}")
    except Exception:
        pass
    return jsonify({"message": "Interview scheduled"})

@app.post("/api/select_student")
def select_student():
    data = request.get_json() or {}
    app_obj = Application.query.get(data.get("id"))
    
    if not app_obj:
        return jsonify({"message": "Application not found"}), 404
        
    app_obj.status = "selected"
    database.session.commit()
    
    try:
        create_notification("student", app_obj.student_id, f"Congratulations — you were selected for job id {app_obj.job_id}")
    except Exception:
        pass
    return jsonify({"message": "Student selected"})

@app.post("/api/export_csv")
def export_csv():
    role = session.get("role")
    uid = session.get("user_id")
    
    if role != "student" or not uid:
        return jsonify({"message": "Unauthorized"}), 403
        
    # Trigger the background celery task
    export_applications_csv.delay(uid)
    
    return jsonify({"message": "Export started! Check your notifications in a few moments."}), 200

@app.get("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)

@app.get("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)