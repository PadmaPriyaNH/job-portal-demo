import os
import requests
from datetime import datetime, timedelta
from PyPDF2 import PdfReader
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def extract_text_from_pdf(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        return text.strip()
    except Exception as e:
        raise ValueError(f"PDF read failed: {str(e)}")

def call_gemini_api(prompt, timeout=20):
    if not GEMINI_API_KEY:
        return None
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.0-pro-latest:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "safetySettings": [
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        ]
    }
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except:
        pass
    return None

def extract_skills_fallback(text):
    keywords = ["Python", "Java", "JavaScript", "Flask", "React", "SQL", "Git", "Docker", "AWS", "REST", "API", "Machine Learning", "Communication", "Problem Solving"]
    found = [k for k in keywords if k.lower() in text.lower()]
    return ", ".join(found[:10]) if found else "No relevant skills detected"

def analyze_candidate(resume_text, github_url=""):
    # Skills
    skills = extract_skills_fallback(resume_text)
    ai_skills = call_gemini_api(f"Extract only technical and soft skills as comma-separated list. Resume: {resume_text[:1500]}")
    if ai_skills:
        skills = ai_skills

    # Communication Score
    comm_score = 65.0
    ai_comm = call_gemini_api(f"Rate resume clarity 0-100. Only number: {resume_text[:500]}")
    if ai_comm:
        try:
            comm_score = float(ai_comm.strip())
        except:
            pass

    # GitHub Analysis
    tech_score = 50.0
    github_summary = "Not provided"
    if github_url:
        try:
            username = github_url.strip('/').split('/')[-1]
            repos = requests.get(f"https://api.github.com/users/{username}/repos?per_page=100", timeout=8).json()
            recent_pushes = 0
            langs = set()
            if isinstance(repos, list):
                for r in repos:
                    if r.get('language'):
                        langs.add(r['language'])
                    pushed_at = r.get('pushed_at')
                    if pushed_at:
                        # Count pushes in last 90 days
                        try:
                            dt = datetime.strptime(pushed_at, "%Y-%m-%dT%H:%M:%SZ")
                            if datetime.utcnow() - dt <= timedelta(days=90):
                                recent_pushes += 1
                        except Exception:
                            pass
                repo_count = len(repos)
                lang_count = len(langs)
                activity_bonus = min(30, recent_pushes * 2)
                tech_score = min(100.0, 40 + repo_count * 2 + lang_count * 6 + activity_bonus)
                github_summary = f"Repos: {repo_count}, Recent active repos: {recent_pushes}, Languages: {', '.join(sorted(langs)) if langs else 'None'}"
        except Exception:
            pass

    # Feedback
    feedback = "Great technical profile! Add live project links to stand out."
    if "Python" in skills:
        feedback = "Strong Python skills! Showcase Flask/Django projects."

    return {
        "skills": skills,
        "tech_score": round(tech_score, 1),
        "comm_score": round(comm_score, 1),
        "github_summary": github_summary,
        "feedback": feedback
    }