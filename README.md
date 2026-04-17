# CollabSpace


## 🚀 Live Demo
👉 [Click here to view the project](https://collabspace-barr.onrender.com/)



**CollabSpace** is a comprehensive, role-based project management and student evaluation platform. Designed for academic and collaborative environments, it provides real-time task tracking, automated grading algorithms, time monitoring, and AI-assisted tools for cross-functional teams consisting of Students, Team Leaders, and Mentors.

---

## 🚀 Features

### Security & Access Control
* **Robust Authentication:** Secure login, registration, and session management using hashed credentials.
* **Role-Based Access Control (RBAC):** Strict permissions dividing users into **Students**, **Mentors**, and **Team Leaders**, ensuring tailored dashboards and secure data visibility.

### Real-Time Task Management
* **Interactive Kanban Board:** Visualize workflow through To-Do, In-Progress, and Done columns.
* **Live Synchronization:** Powered by WebSockets, moving a card updates the screen for all team members instantly without refreshing.

### Advanced Time Tracking
* **Task Estimates vs. Actuals:** Admins can assign estimated completion times.
* **Live Timers & Manual Entry:** Students can start a live timer or log manual hours against tasks. Time increments broadcast live to the team.

### Automated Evaluation & Reporting
* **Scoring Algorithm:** An automated backend engine calculates a student's grade mathematically based on:
  - Task completion rates and deadlines (50%)
  - Hours logged against expected estimates (30%)
  - Peer and mentor evaluations (20%)
* **PDF Engine:** Mentors and leaders can easily export professional, automatically-generated PDF evaluations outlining team and individual metrics.

### AI Integration & Async Processing
* **AI Note Analyzer:** Integrated with the Anthropic (Claude) API to automatically generate insights and summaries from group meeting notes.
* **Background Workers:** Heavy tasks (PDF generation, emails, AI processing) are offloaded to Celery/Redis to keep the platform lightning fast.

---

## 🛠️ Technology Stack

**Backend Architecture:**
* **Framework:** Python / Flask
* **Database & ORM:** SQLite (dev) / PostgreSQL (prod), SQLAlchemy
* **Asynchronous Queues:** Celery & Redis
* **Real-time WebSockets:** Flask-SocketIO

**Frontend & Templates:**
* **Rendering Engine:** Jinja2 (Server-Side Rendering)
* **Design:** Vanilla CSS / JavaScript

**Integrations:**
* **AI Engine:** Anthropic API (Claude)
* **Document Generation:** ReportLab
* **Email:** Flask-Mail

---

## ⚙️ Local Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone <repository_url>
   cd collabsapce
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables:**
   Copy the example environment file and fill in your keys (Database URL, Anthropic Key, Redis URL, Flask Secret Key).
   ```bash
   cp .env.example .env
   ```

5. **Initialize Database:**
   ```bash
   flask db upgrade
   ```

6. **Start Redis Server (Required for Celery background tasks):**
   ```bash
   # Run in a separate terminal tab
   redis-server
   ```

7. **Start Celery Worker (Required for background processing):**
   ```bash
   # Run in a separate terminal tab, inside the virtual environment
   celery -A celery_worker.celery worker --loglevel=info
   ```

8. **Start the Flask Application:**
   ```bash
   python run.py
   ```

The application will be available locally at `http://localhost:5000`.

---

## 📁 Folder Structure

```text
collabspace/
│
├── app/                        # Main Application Package
│   ├── api/                    # API Endpoints (v1)
│   ├── models/                 # SQLAlchemy Database Models (user, task, etc.)
│   ├── routes/                 # Flask Blueprints (auth, dashboard, tasks, etc.)
│   ├── sockets/                # Flask-SocketIO event handlers for WebSockets
│   ├── static/                 # Static assets (CSS, JS, images)
│   ├── tasks/                  # Celery background tasks (email_tasks.py)
│   ├── templates/              # Jinja2 HTML Templates
│   └── utils/                  # Helper Python scripts (score engine, decorators, AI parsing)
│
├── tests/                      # Pytest automation suite and mock data
├── migrations/                 # Alembic Database Migration files (auto-generated)
├── venv/                       # Python Virtual Environment
│
├── requirements.txt            # Python Dependencies
├── config.py                   # Application configuration (Dev/Testing/Production modes)
├── run.py                      # Application Entry Point
├── celery_worker.py            # Entry point for Celery Background Workers
└── .env                        # Private Environment Variables
```

---

## 🛡️ License
[Insert License details here, e.g., MIT, Proprietary, etc.]
