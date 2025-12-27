from flask import Flask, render_template, request, jsonify
import json
import random
import requests
import os
from collections import defaultdict
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

# URL of the AI analyzer service (System B)
SYSTEM_B_URL = "http://127.0.0.1:5000/analyze"

# Load interview questions
with open(os.path.join(BASE_DIR, "questions.json"), "r", encoding="utf-8") as f:
    questions_data = json.load(f)

# In-memory user profiles (use a database like SQLite for persistence in production)
user_profiles = {}

# Simple stopword set for concept extraction from questions
STOPWORDS = {
    'what', 'why', 'how', 'when', 'where', 'who', 'whom', 'is', 'are', 'the', 'a', 'an',
    'and', 'or', 'to', 'of', 'in', 'on', 'for', 'with', 'does', 'do', 'you', 'your',
    'explain', 'describe', 'difference', 'between', 'give', 'example', 'examples',
    'tell', 'me', 'about', 'that', 'this', 'it', 'be', 'as', 'at', 'by', 'from',
}

def extract_concept(question_text: str) -> str:
    """Extract a simple concept keyword from the question text."""
    import re
    words = re.sub(r'[^a-zA-Z0-9\s]', ' ', question_text.lower()).split()
    filtered = [w for w in words if w not in STOPWORDS and len(w) >= 3]
    return filtered[0] if filtered else (words[0] if words else "general")


def get_user_id():
    """Get or create a user ID using cookies."""
    return request.cookies.get('user_id') or str(uuid.uuid4())

# --- Routes ---

@app.route("/")
def welcome():
    """Welcome page."""
    return render_template("welcome.html")

@app.route("/interview")
def interview():
    """Interview practice page."""
    categories = list(questions_data.keys())
    return render_template("index.html", categories=categories)

@app.route("/thankyou")
def thank_you():
    """Thank you page after interview."""
    return render_template("thankyou.html")

@app.route("/dashboard")
def dashboard():
    """User progress dashboard."""
    user_id = request.cookies.get('user_id')
    if not user_id or user_id not in user_profiles:
        # No data → show empty but valid dashboard
        return render_template("dashboard.html", user_skills={}, weakest_concept=None, recommended_questions=[])

    profile = user_profiles[user_id]
    concept_scores = profile.get("concept_scores", defaultdict(list))
    
    # Calculate average scores per concept (only if scores exist)
    user_skills = {}
    for concept, scores in concept_scores.items():
        if scores:
            avg_score = round(sum(scores) / len(scores), 1)
            if avg_score > 0:  # Avoid zero-initialized scores
                user_skills[concept] = avg_score
    
    # Find weakest concept and recommend questions
    weakest_concept = None
    recommended_questions = []
    if user_skills:
        weakest_concept = min(user_skills, key=user_skills.get)
        # Find up to 3 questions related to the weakest concept
        for category in questions_data.values():
            for q in category:
                if weakest_concept.lower() in q["question"].lower():
                    recommended_questions.append(q["question"])
                    if len(recommended_questions) >= 3:
                        break
            if len(recommended_questions) >= 3:
                break

    return render_template(
        "dashboard.html",
        user_skills=user_skills,
        weakest_concept=weakest_concept,
        recommended_questions=recommended_questions[:3]
    )

@app.route("/get-question", methods=["POST"])
def get_question():
    """Fetch an adaptive question based on user's weakest area."""
    user_id = get_user_id()
    if user_id not in user_profiles:
        user_profiles[user_id] = {"concept_scores": defaultdict(list), "used_by_cat": {}, "last_question_by_cat": {}}
    
    profile = user_profiles[user_id]
    category = request.json.get("category")
    
    if not category or category not in questions_data:
        return jsonify({"message": "Invalid category."})

    all_questions = questions_data[category]

    # Track used questions per category to avoid immediate repeats
    used_by_cat = profile.setdefault("used_by_cat", {})
    last_q_by_cat = profile.setdefault("last_question_by_cat", {})
    used = set(used_by_cat.get(category, []))

    # Build candidate pool excluding used questions
    candidates = [q for q in all_questions if q["question"] not in used]

    # Avoid repeating the very last question if possible
    last_q = last_q_by_cat.get(category)
    if last_q and len(candidates) > 1:
        candidates = [q for q in candidates if q["question"] != last_q] or candidates

    # If all questions have been used, reset and start fresh
    if not candidates:
        used_by_cat[category] = []
        used = set()
        candidates = list(all_questions)

    # Score candidates by user's weakest concepts first
    scored_questions = []
    for q in candidates:
        concept = extract_concept(q["question"])
        scores = profile["concept_scores"].get(concept, [5.0])  # Default to medium score
        avg_score = sum(scores) / len(scores)
        scored_questions.append((q, avg_score))

    # Sort by lowest average score (target weaknesses) and choose randomly among the bottom 3
    scored_questions.sort(key=lambda x: x[1])
    k = min(3, len(scored_questions))
    selected = random.choice(scored_questions[:k])[0]

    # Mark as used and remember last question for this category
    used_by_cat.setdefault(category, []).append(selected["question"])
    last_q_by_cat[category] = selected["question"]
    
    # Set cookie to persist user session
    resp = jsonify({"question": selected["question"]})
    resp.set_cookie('user_id', user_id, max_age=60*60*24*30)  # 30 days
    return resp

@app.route("/submit-answer", methods=["POST"])
def submit_answer():
    """Submit answer for AI analysis and track progress."""
    data = request.json
    question = data.get("question")
    answer = data.get("answer")

    if not question or not answer:
        return jsonify({"error": "Missing question or answer."}), 400

    try:
        # Send to AI analyzer (System B)
        response = requests.post(SYSTEM_B_URL, json={"question": question, "answer": answer}, timeout=15)
        if response.status_code == 200:
            result = response.json()
            
            # Extract concept from question (same logic as in /get-question)
            concept = extract_concept(question)
            
            # Save score to user profile for adaptive learning
            user_id = request.cookies.get('user_id')
            if user_id and user_id in user_profiles:
                profile = user_profiles[user_id]
                score = result.get("score", 0)
                if isinstance(score, (int, float)) and score > 0:
                    profile["concept_scores"][concept].append(float(score))
            
            return jsonify(result)
        else:
            return jsonify({"error": "Analysis service returned an error."}), 500
    except Exception as e:
        return jsonify({"error": "AI analysis service is unreachable. Please ensure analyzer.py is running."}), 500

# --- Run App ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)