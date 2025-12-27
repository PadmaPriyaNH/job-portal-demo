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

### 1) Clone and create a virtual environment
```bash
git clone <your-repo-url>.git
cd job-portal-demo
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate
```

### 2) Install dependencies
```bash
pip install -r requirements.txt
```

### 3) Create a .env file (not committed)
```bash
# Required for AI extraction (optional; app works without it)
GEMINI_API_KEY=your-gemini-api-key

# Optional shared secret to protect interview callbacks
INTERVIEW_SECRET=dev-shared-secret
```

### 4) Run locally
```bash
python app.py
```
- App: http://127.0.0.1:5000/

## Data & directories
- SQLite DB lives under instance/jobportal.db (auto-created). It is ignored by Git.
- User uploads stored under uploads/ (ignored by Git).

## Interview Interface Integration
- Recruiter can Start Interview on Applicants page, which opens an external interviewer app.
- On completion, the interviewer app should call back:
  - POST http://<your-app-host>/interview/callback
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
```
web: gunicorn app:app
```
- Ensure `gunicorn` is in requirements.txt (already added)
- Set environment variables (GEMINI_API_KEY, INTERVIEW_SECRET) in the hosting platform

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
```
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
- Do not commit `.env` or database files.
- For production, run behind gunicorn (debug disabled).
- If you change the interviewer app host/port, update the Start Interview link in `templates/applicants.html`.

## License
MIT
