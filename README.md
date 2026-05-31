# Placement Portal v2

A robust and scalable Placement Portal application built using Flask, SQLAlchemy, and Celery. It streamlines the placement process by seamlessly connecting students, companies, and placement staff (admins). 

## 🚀 Features

- **Role-Based Access Control:** Separate dashboards, permissions, and functionalities for Students, Companies, and Employees (Admins/Staff).
- **User Approval Workflow:** Admins can approve, reject, or block users (students, companies, and staff) to maintain platform integrity.
- **Job/Drive Management:** Companies can post job openings and placement drives. Admins review and approve them before they become visible to students.
- **Student Profiles & Applications:** Students can update their academic profiles (CGPA, branch, passing year), browse approved jobs, and submit applications.
- **Background Tasks & CRON Jobs:** Leverages Celery and Redis to handle asynchronous tasks like sending daily deadline reminders and generating monthly admin reports.
- **Email Notifications:** Integrated with an SMTP server (defaults to local MailHog/Mailpit on port `1025`) for email simulation.
- **Real-Time Notifications:** In-app notification system to alert users about application updates, approvals, and upcoming deadlines.
- **Asynchronous CSV Exports:** Export student applications seamlessly via Celery background tasks.
- **JWT Authentication:** Secure token-based API authentication.

## 🛠️ Tech Stack

- **Backend:** Flask, Python 3
- **Database:** SQLite (via Flask-SQLAlchemy)
- **Task Queue / Asynchronous Workers:** Celery
- **Message Broker & Caching:** Redis (via Flask-Caching)
- **Frontend:** HTML, CSS, JavaScript (Jinja2 Templates)
- **Authentication:** JWT (JSON Web Tokens)

## 🗂️ Project Structure

```text
placement_portal_v2/
├── controller/
│   ├── model.py            # SQLAlchemy Database Models (Student, Company, Job, etc.)
│   ├── run.py              # Flask Application Factory, Routes, & Celery Tasks
│   └── __init__.py         
├── instance/               # SQLite Database files (users.db)
├── static/                 # Static assets (CSS, JS, Images)
├── templates/              # HTML Templates (login, home, monthly_report, etc.)
└── project_report.pdf      # Detailed project documentation
```

## ⚙️ Setup & Installation

### 1. Prerequisites
- Python 3.8+
- Redis Server (Must be running on `localhost:6379`)
- MailHog or Mailpit (Optional, for local email testing on port `1025`)

### 2. Install Dependencies
Ensure you have the required Python packages installed. You can install them via pip:
```bash
pip install Flask Flask-SQLAlchemy Flask-Caching celery PyJWT Werkzeug
```
*(Note: If a `requirements.txt` is present in the repository, you can simply run `pip install -r requirements.txt`)*

### 3. Start Redis Server
Ensure Redis is running in the background, as it serves as the message broker for Celery and the caching backend for Flask.
```bash
# On Linux/macOS
redis-server
```

### 4. Run the Flask Application
Start the main web server. The database tables and default admin will be automatically created on the first run.
```bash
cd controller
python run.py
```
*(Alternatively, you can run it via `flask --app run run` depending on your environment setup)*

### 5. Run Celery Worker
In a new terminal window, navigate to the `controller` directory and start the Celery worker to process background tasks (like CSV exports and asynchronous emails):
```bash
cd controller
celery -A run.celery worker --loglevel=info
```
*(Note: On Windows, the worker pool is set to 'solo' in the configuration to prevent execution errors).*

### 6. Run Celery Beat (For Scheduled Tasks)
In another terminal window, start Celery Beat for scheduled CRON jobs (e.g., daily deadline reminders, monthly reports):
```bash
cd controller
celery -A run.celery beat --loglevel=info
```

## 👤 Default Accounts
Upon initial startup, the application creates a default admin account if it does not already exist:
- **Username:** `admin`
- **Password:** `admin123`
- **Role:** Admin (Full Access)

## 📡 Key API Endpoints
- `POST /api/register` - Register a new Student, Company, or Employee
- `POST /api/login` - Authenticate and receive a JWT
- `GET /api/me` - Get current user profile details
- `POST /api/post_job` - (Company) Submit a new job for admin approval
- `GET /api/jobs` - View approved jobs
- `POST /api/approve_user` - (Admin) Approve a pending user account
