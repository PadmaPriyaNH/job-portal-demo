from flask import Flask, request, render_template, redirect, url_for, session, jsonify, flash, Response
from models import db, User, CandidateProfile, Job, Application, Review
from utils import analyze_candidate, extract_text_from_pdf
import os
import os as _os
import csv
import io
import re
from datetime import datetime as dt

app = Flask(__name__)
INTERVIEW_APP_URL = "http://127.0.0.1:8000/interview"
INTERVIEW_SECRET = _os.getenv("INTERVIEW_SECRET", "")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///jobportal.db'
app.config['SECRET_KEY'] = 'demo-secret-key-for-interview'
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)

with app.app_context():
    db.create_all()

# ===== Auth Routes =====
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        if User.query.filter_by(email=email).first():
            flash("Email already exists", "error")
            return redirect(url_for('signup'))
        user = User(email=email, password=password, role=role)
        db.session.add(user)
        db.session.commit()
        session['user_id'] = user.id
        session['role'] = role
        session['email'] = email
        flash("Signup successful. Welcome!", "success")
        return redirect(url_for('dashboard'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email'], password=request.form['password']).first()
        if user:
            session['user_id'] = user.id
            session['role'] = user.role
            session['email'] = user.email
            return redirect(url_for('dashboard'))
        flash("Invalid email or password", "error")
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for('login'))

# ===== Dashboard =====
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if user.role == 'candidate':
        jobs = Job.query.all()
        applications = Application.query.filter_by(candidate_id=user.id).all()
        return render_template('candidate_dashboard.html', jobs=jobs, applications=applications)
    else:
        jobs = Job.query.filter_by(recruiter_id=user.id).all()
        return render_template('recruiter_dashboard.html', jobs=jobs)

# ===== Candidate Profile =====
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if session.get('role') != 'candidate':
        return redirect(url_for('login'))
    user_id = session['user_id']
    profile = CandidateProfile.query.filter_by(user_id=user_id).first()
    if request.method == 'POST':
        resume = request.files.get('resume')
        github = request.form.get('github_url', '').strip()
        linkedin = request.form.get('linkedin_url', '').strip()
        manual = request.form.get('manual_skills', '').strip()
        if not profile:
            profile = CandidateProfile(user_id=user_id)
        # Save new resume if provided
        resume_text = "No content"
        if resume and getattr(resume, 'filename', ''):
            path = os.path.join(app.config['UPLOAD_FOLDER'], resume.filename)
            resume.save(path)
            profile.resume_path = path
        # Load resume text from stored resume if available
        if profile.resume_path and os.path.exists(profile.resume_path):
            try:
                resume_text = extract_text_from_pdf(profile.resume_path) or "No content"
            except Exception:
                resume_text = "No content"
                flash("We couldn't parse your resume PDF. You can still add skills or try another file.", "error")
        # Analyze to compute scores (uses GitHub too)
        result = analyze_candidate(resume_text, github or (profile.github_url or ""))
        # Merge skills: existing + AI/extracted + manual
        existing_skills = profile.extracted_skills or ""
        extracted = result.get('skills') or ""
        combined = [s.strip() for s in (existing_skills + "," + extracted + "," + manual).split(",") if s.strip()]
        seen = set()
        dedup = []
        for s in combined:
            k = s.lower()
            if k not in seen:
                seen.add(k)
                dedup.append(s)
        profile.extracted_skills = ", ".join(dedup[:50]) if dedup else existing_skills
        profile.github_url = github or profile.github_url
        profile.linkedin_url = linkedin or profile.linkedin_url
        # Update scores
        if result:
            profile.tech_score = result.get('tech_score', profile.tech_score or 0)
            profile.comm_score = result.get('comm_score', profile.comm_score or 0)
        db.session.add(profile)
        db.session.commit()
        # Update funnel for all applications of this candidate
        apps = Application.query.filter_by(candidate_id=user_id).all()
        for a in apps:
            auto_update_funnel(a.id)
        flash("Profile saved successfully", "success")
        return redirect(url_for('dashboard'))
    return render_template('profile.html', profile=profile)

# ===== Apply to Job =====
@app.route('/apply/<int:job_id>')
def apply(job_id):
    if session.get('role') != 'candidate':
        flash("Candidates only. Please log in as a candidate.", "error")
        return redirect(url_for('login'))
    if Application.query.filter_by(candidate_id=session['user_id'], job_id=job_id).first():
        flash("You have already applied to this job.", "error")
        return redirect(url_for('dashboard'))
    app_record = Application(candidate_id=session['user_id'], job_id=job_id)
    db.session.add(app_record)
    db.session.commit()
    auto_update_funnel(app_record.id)
    flash("Application submitted successfully", "success")
    return redirect(url_for('dashboard'))

# ===== Recruiter: Post Job =====
@app.route('/post_job', methods=['GET', 'POST'])
def post_job():
    if session.get('role') != 'recruiter':
        flash("Recruiters only. Please log in as a recruiter.", "error")
        return redirect(url_for('login'))
    if request.method == 'POST':
        job = Job(
            title=request.form['title'],
            description=request.form['description'],
            recruiter_id=session['user_id']
        )
        db.session.add(job)
        db.session.commit()
        flash("Job posted successfully", "success")
        return redirect(url_for('dashboard'))
    return render_template('post_job.html')

# ===== View Applicants =====
@app.route('/applicants/<int:job_id>')
def applicants(job_id):
    job = Job.query.get(job_id)
    if not job or job.recruiter_id != session.get('user_id'):
        flash("Unauthorized to view applicants for this job.", "error")
        return redirect(url_for('dashboard'))
    apps = Application.query.filter_by(job_id=job_id).all()
    candidates = []
    for app in apps:
        user = User.query.get(app.candidate_id)
        profile = CandidateProfile.query.filter_by(user_id=user.id).first()
        candidates.append({
            'email': user.email,
            'status': app.status,
            'tech_score': profile.tech_score if profile else 0,
            'comm_score': profile.comm_score if profile else 0,
            'application_id': app.id
        })
    # ✅ PASS INTERVIEW_APP_URL TO TEMPLATE (THIS IS THE ONLY CHANGE)
    return render_template('applicants.html', job=job, candidates=candidates, INTERVIEW_APP_URL=INTERVIEW_APP_URL)

# ===== Add Review =====
@app.route('/application/<int:app_id>')
def application_detail(app_id):
    if session.get('role') != 'candidate' or session.get('user_id') is None:
        return redirect(url_for('login'))
    app_rec = Application.query.get(app_id)
    if not app_rec or app_rec.candidate_id != session.get('user_id'):
        flash("Unauthorized to view this application.", "error")
        return redirect(url_for('dashboard'))
    job = Job.query.get(app_rec.job_id)
    reviews = Review.query.filter_by(application_id=app_id).all()
    return render_template('application_detail.html', application=app_rec, job=job, reviews=reviews)

@app.route('/interview/callback', methods=['POST'])
def interview_callback():
    # Optional shared secret validation
    token = request.headers.get('X-Interview-Token', '')
    if INTERVIEW_SECRET and token != INTERVIEW_SECRET:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    app_id = data.get('app_id')
    reviewer_type = data.get('reviewer_type')
    score = data.get('score')
    comment = data.get('comment', '')
    if not all([app_id, reviewer_type, isinstance(score, (int, float))] or [False]):
        return jsonify({"error": "Invalid payload"}), 400
    app_rec = Application.query.get(app_id)
    if not app_rec:
        return jsonify({"error": "Application not found"}), 404
    review = Review(application_id=app_id, reviewer_type=reviewer_type, score=float(score), comment=comment)
    db.session.add(review)
    db.session.commit()
    # Update funnel based on averages
    all_reviews = Review.query.filter_by(application_id=app_id).all()
    tech_scores = [r.score for r in all_reviews if r.reviewer_type == 'tech']
    hr_scores = [r.score for r in all_reviews if r.reviewer_type == 'hr']
    avg_tech = sum(tech_scores) / len(tech_scores) if tech_scores else 0
    avg_hr = sum(hr_scores) / len(hr_scores) if hr_scores else 0
    if avg_tech >= 70 and avg_hr >= 70:
        app_rec.status = "Selected"
    elif avg_tech >= 60 and avg_hr >= 60:
        app_rec.status = "HR Checked"
    elif avg_tech >= 60:
        app_rec.status = "Technical Checked"
    elif all_reviews:
        app_rec.status = "Shortlisted"
    db.session.commit()
    return jsonify({"status": "ok", "application_status": app_rec.status}), 200

@app.route('/review/<int:app_id>', methods=['POST'])
def add_review(app_id):
    if session.get('role') != 'recruiter':
        flash("Recruiters only. Please log in as a recruiter.", "error")
        return redirect(url_for('login'))
    review = Review(
        application_id=app_id,
        reviewer_type=request.form['reviewer_type'],
        score=float(request.form['score']),
        comment=request.form['comment']
    )
    db.session.add(review)
    db.session.commit()
    # Recalculate hiring funnel based on reviews
    app_rec = Application.query.get(app_id)
    all_reviews = Review.query.filter_by(application_id=app_id).all()
    tech_scores = [r.score for r in all_reviews if r.reviewer_type == 'tech']
    hr_scores = [r.score for r in all_reviews if r.reviewer_type == 'hr']
    avg_tech = sum(tech_scores)/len(tech_scores) if tech_scores else 0
    avg_hr = sum(hr_scores)/len(hr_scores) if hr_scores else 0
    if avg_tech >= 70 and avg_hr >= 70:
        app_rec.status = "Selected"
    elif avg_tech >= 60 and avg_hr >= 60:
        app_rec.status = "HR Checked"
    elif avg_tech >= 60:
        app_rec.status = "Technical Checked"
    elif all_reviews:
        app_rec.status = "Shortlisted"
    db.session.commit()
    flash("Review submitted", "success")
    return redirect(url_for('applicants', job_id=request.form['job_id']))

# ===== Hiring Funnel Automation =====
def auto_update_funnel(app_id):
    app = Application.query.get(app_id)
    profile = CandidateProfile.query.filter_by(user_id=app.candidate_id).first()
    if not profile:
        return
    if profile.tech_score >= 70 and profile.comm_score >= 70:
        app.status = "Selected"
    elif profile.tech_score >= 60 and profile.comm_score >= 60:
        app.status = "HR Checked"
    elif profile.tech_score >= 60:
        app.status = "Technical Checked"
    elif profile.tech_score > 0:
        app.status = "Shortlisted"
    db.session.commit()

# ===== Dashboards =====
@app.route('/leaderboard')
def leaderboard():
    skill = request.args.get('skill', '').strip()
    query = CandidateProfile.query
    if skill:
        query = query.filter(CandidateProfile.extracted_skills.ilike(f"%{skill}%"))
    profiles = query.order_by(CandidateProfile.tech_score.desc()).limit(50).all()
    candidates = []
    for p in profiles:
        user = User.query.get(p.user_id)
        candidates.append({
            'email': user.email,
            'tech_score': p.tech_score,
            'skills': p.extracted_skills
        })
    return render_template('leaderboard.html', candidates=candidates, skill=skill)

@app.route('/feedback/<int:job_id>')
def feedback_view(job_id):
    job = Job.query.get(job_id)
    if not job or job.recruiter_id != session.get('user_id'):
        flash("Unauthorized to view feedback for this job.", "error")
        return redirect(url_for('dashboard'))
    apps = Application.query.filter_by(job_id=job_id).all()
    data = []
    for app in apps:
        user = User.query.get(app.candidate_id)
        reviews = Review.query.filter_by(application_id=app.id).all()
        data.append({
            'candidate': user.email,
            'status': app.status,
            'reviews': reviews
        })
    return render_template('feedback.html', job=job, data=data)

@app.route('/export/candidates.csv')
def export_candidates_csv():
    if session.get('role') != 'recruiter':
        flash("Recruiters only. Please log in as a recruiter.", "error")
        return redirect(url_for('dashboard'))

    users = User.query.filter_by(role='candidate').all()

    # Build dataset
    data = []
    for u in users:
        p = CandidateProfile.query.filter_by(user_id=u.id).first()
        tech = float(p.tech_score) if p and p.tech_score is not None else 0.0
        comm = float(p.comm_score) if p and p.comm_score is not None else 0.0
        composite = round((tech + comm) / 2.0, 2)

        resume_filename = "Not uploaded"
        resume_text = ""
        if p and p.resume_path and os.path.exists(p.resume_path):
            resume_filename = os.path.basename(p.resume_path)
            try:
                resume_text = extract_text_from_pdf(p.resume_path) or ""
            except Exception:
                resume_text = ""

        # Try to extract phone from resume text
        phone = ""
        if resume_text:
            m = re.search(r'(\+?\d[\d \-\(\)]{7,}\d)', resume_text)
            if m:
                phone = m.group(1).strip()

        # Leadership inference from resume
        leadership = ""
        if resume_text:
            t = resume_text.lower()
            indicators = ['team lead', 'lead developer', 'led ', 'lead ', 'managed', 'manager', 'mentored', 'supervised', 'head of']
            leadership = "Yes" if any(ind in t for ind in indicators) else "No"

        # Applications summary
        apps = Application.query.filter_by(candidate_id=u.id).order_by(Application.created_at.desc()).all()
        num_jobs = len({a.job_id for a in apps}) if apps else 0
        current_status = apps[0].status if apps else "Applied"

        # Latest review across all applications (by highest ID)
        latest_review = ""
        if apps:
            app_ids = [a.id for a in apps]
            r = Review.query.filter(Review.application_id.in_(app_ids)).order_by(Review.id.desc()).first()
            if r:
                snippet = (r.comment or "").strip().replace('\n', ' ')
                if len(snippet) > 100:
                    snippet = snippet[:100] + "..."
                latest_review = f"{r.reviewer_type.upper()} {int(r.score) if r.score is not None else ''}: {snippet}"

        linkedin = p.linkedin_url if p and p.linkedin_url else ""
        github = p.github_url if p and p.github_url else ""
        merged_skills = p.extracted_skills if p and p.extracted_skills else ""

        # Placeholders for fields not stored separately
        manual_skills = ""
        ai_skills = ""
        candidate_name = ""

        data.append({
            "name": candidate_name,
            "email": u.email,
            "phone": phone,
            "linkedin": linkedin,
            "github": github,
            "resume": resume_filename,
            "manual_skills": manual_skills,
            "ai_skills": ai_skills,
            "merged_skills": merged_skills,
            "tech_score": tech,
            "comm_score": comm,
            "composite": composite,
            "status": current_status,
            "num_jobs": num_jobs,
            "latest_review": latest_review,
        })

    # Dense ranking based on composite score (desc)
    scores = sorted({row["composite"] for row in data}, reverse=True)
    rank_map = {score: idx + 1 for idx, score in enumerate(scores)}
    for row in data:
        row["rank"] = rank_map[row["composite"]]

    # Sort by composite desc for output
    data.sort(key=lambda r: r["composite"], reverse=True)

    # Generate CSV
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow([
        "Candidate Name",
        "Email",
        "Phone",
        "LinkedIn URL",
        "GitHub URL",
        "Uploaded Resume Filename",
        "Manual Skills",
        "AI-Extracted Skills",
        "Merged & Deduplicated Skills",
        "GitHub Technical Score",
        "Communication Score",
        "Total Composite Score",
        "Overall Rank",
        "Current Application Status",
        "Number of Jobs Applied",
        "Latest Interview Review"
    ])

    for row in data:
        writer.writerow([
            row["name"],
            row["email"],
            row["phone"],
            row["linkedin"],
            row["github"],
            row["resume"],
            row["manual_skills"] or "",
            row["ai_skills"] or "",
            row["merged_skills"] or "",
            row["tech_score"],
            row["comm_score"],
            row["composite"],
            row["rank"],
            row["status"],
            row["num_jobs"],
            row["latest_review"]
        ])

    csv_data = output.getvalue()
    response = Response(csv_data, mimetype='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename=candidates_export_{dt.utcnow().strftime("%Y%m%d")}.csv'
    return response

if __name__ == '__main__':
    app.run(debug=True)