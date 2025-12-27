from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'candidate' or 'recruiter'

class CandidateProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    resume_path = db.Column(db.String(200))
    github_url = db.Column(db.String(200))
    linkedin_url = db.Column(db.String(200))
    extracted_skills = db.Column(db.Text)
    tech_score = db.Column(db.Float, default=0.0)
    comm_score = db.Column(db.Float, default=0.0)

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    recruiter_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'))
    status = db.Column(db.String(30), default="Applied")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'))
    reviewer_type = db.Column(db.String(20))  # 'tech' or 'hr'
    score = db.Column(db.Float)
    comment = db.Column(db.Text)