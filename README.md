# AI Job Portal Demo

A compact, end-to-end job portal with Candidate and Recruiter modules, AI-assisted skill extraction, GitHub-based technical scoring, automated hiring funnel, reviewer feedback, and skill leaderboard.

## Features
- Auth: Candidate and Recruiter login/signup with session handling
- Candidate module:
  - Upload resume (PDF), GitHub & LinkedIn links
  - Add manual skills; AI-extracted + manual skills merged and deduped
  - View jobs and apply
  - View application details and interview reviews
- Recruiter module:
  - Post jobs and view applicants
  - Add Tech/HR reviews with scores and comments
  - Start interview in external interview interface (integrated via callback)
- AI & Scoring:
  - Resume parsing (PyPDF2) + Gemini API skill extraction (fallback when absent)
  - GitHub analysis: repos, languages, recent activity → tech score (0–100)
  - Communication score via Gemini (fallback default)
- Hiring funnel automation:
  - Applied → Shortlisted → Technical Checked → HR Checked → Selected
  - Auto updates on application, profile save, and review/callback
- Dashboards:
  - Skill leaderboard (filter by skill)
  - Recruiter feedback view per job
- Modern UI/UX based on a clean, accessible light theme

## Tech Stack
- Python 3.11+
- Flask, SQLAlchemy
- PyPDF2, requests, python-dotenv
- Optional: Gemini API (google-generativeai)
- Production server: gunicorn

## Quickstart

> 💡 **This project has TWO parts**:  
> 1. **Main Job Portal** (Flask app)  
> 2. **Interview Interface** (separate Flask app in `interview-interface/AI-Interview-Coach`)

### 1) Clone and create a virtual environment
```bash
git clone https://github.com/PadmaPriyaNH/job-portal-demo.git
cd job-portal-demo
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate
```

### 2) Install dependencies for BOTH apps
```bash
# Install main portal dependencies
pip install -r requirements.txt

# Install interview interface dependencies (if it has its own requirements.txt)
cd interview-interface/AI-Interview-Coach
# If there's a requirements.txt, run:
# pip install -r requirements.txt
# Otherwise, ensure Flask is installed (already in main env)
cd ../..
```

### 3) Create a `.env` file (not committed)
```env
# Required for AI extraction (optional; app works without it)
GEMINI_API_KEY=your-gemini-api-key

# Optional shared secret to protect interview callbacks
INTERVIEW_SECRET=dev-shared-secret
```

### 4) Run the apps in TWO separate terminals

#### 🔹 Terminal 1: Start the Interview Interface
```bash
cd interview-interface/AI-Interview-Coach
python wsgi.py
```
✅ Expected output: `Running on http://127.0.0.1:8000/`

#### 🔹 Terminal 2: Start the Main Job Portal
```bash
# Make sure you're back in the main project folder
cd job-portal-demo
python app.py
```
✅ Expected output: `Running on http://127.0.0.1:5000`

### 5) Use the app
- **Job Portal**: http://127.0.0.1:5000/
- **Interview Interface**: Automatically opens in a new tab when a recruiter clicks **“Start Interview”** on the Applicants page

> 📌 The “Start Interview” button passes `app_id`, `candidate_email`, and `job_title` to the interview interface for context.

## Data & directories
- SQLite DB lives under `instance/jobportal.db` (auto-created). It is ignored by Git.
- User uploads stored under `uploads/` (ignored by Git).

## Interview Interface Integration
- Recruiter can Start Interview on Applicants page, which opens an external interviewer app.
- On completion, the interviewer app should call back:
  - POST http://127.0.0.1:5000/interview/callback
  - Headers: `Content-Type: application/json`
  - If using shared secret: `X-Interview-Token: <INTERVIEW_SECRET>`
  - Payload example:
```json
{
  "app_id": 42,
  "reviewer_type": "tech",
  "score": 82.5,
  "comment": "Strong on problem solving and Python."
}
```
- The portal persists the review and updates the hiring funnel automatically.

## Deploying

### Using Gunicorn (Render/Railway/Heroku-like)
- Procfile is included:
```procfile
web: gunicorn app:app
```
- Ensure `gunicorn` is in `requirements.txt` (already added)
- Set environment variables (`GEMINI_API_KEY`, `INTERVIEW_SECRET`) in the hosting platform

### Render.com
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app`
- Set environment variables in the Render dashboard

### Docker (optional)
Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
```
Create `.dockerignore`:
```gitignore
.env
__pycache__/
*.pyc
instance/
uploads/
.venv/
.DS_Store
.vscode/
.idea/
```
Build & run:
```bash
docker build -t job-portal-demo .
docker run -p 5000:5000 --env-file .env job-portal-demo
```

## Notes
- Do not commit `.env`, database files (`instance/`), or uploads (`uploads/`).
- For production, run behind gunicorn with `debug=False`.
- Both apps must be running **simultaneously** for the “Start Interview” feature to work.
- The interview interface is designed as a microservice — it can be replaced or extended independently.

## License
MIT
