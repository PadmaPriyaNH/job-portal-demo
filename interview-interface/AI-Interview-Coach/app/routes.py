import os
import json
import logging
from typing import Dict, List
from flask import Blueprint, render_template, request, jsonify, current_app, make_response
from collections import defaultdict

from .utils.text import extract_concept
from .ai.analyzer_service import analyze_answer

bp = Blueprint('main', __name__)

logger = logging.getLogger(__name__)


def _load_questions() -> Dict[str, List[Dict[str, str]]]:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(base_dir, "questions.json"), "r", encoding="utf-8") as f:
        return json.load(f)


questions_data = _load_questions()

# In-memory user profiles (use a database like SQLite/Redis for production)
user_profiles: Dict[str, Dict] = {}


def get_user_id_from_request() -> str:
    return request.cookies.get('user_id') or os.urandom(16).hex()


@bp.route("/")
def welcome():
    return render_template("welcome.html")


@bp.route("/interview")
def interview():
    categories = list(questions_data.keys())
    return render_template("index.html", categories=categories)


@bp.route("/thankyou")
def thank_you():
    return render_template("thankyou.html")


@bp.route("/dashboard")
def dashboard():
    user_id = request.cookies.get('user_id')
    if not user_id or user_id not in user_profiles:
        return render_template("dashboard.html", user_skills={}, weakest_concept=None, recommended_questions=[])

    profile = user_profiles[user_id]
    concept_scores = profile.get("concept_scores", defaultdict(list))

    user_skills = {}
    for concept, scores in concept_scores.items():
        if scores:
            avg_score = round(sum(scores) / len(scores), 1)
            if avg_score > 0:
                user_skills[concept] = avg_score

    weakest_concept = None
    recommended_questions: List[str] = []
    if user_skills:
        weakest_concept = min(user_skills, key=user_skills.get)
        # Match questions whose extracted concept equals the weakest concept for better precision
        for category in questions_data.values():
            for q in category:
                if extract_concept(q["question"]) == weakest_concept:
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


@bp.route("/get-question", methods=["POST"])
def get_question():
    user_id = get_user_id_from_request()
    if user_id not in user_profiles:
        user_profiles[user_id] = {"concept_scores": defaultdict(list), "used_by_cat": {}, "last_question_by_cat": {}}

    profile = user_profiles[user_id]
    body = request.get_json(silent=True) or {}
    category = body.get("category")

    if not category or category not in questions_data:
        return jsonify({"message": "Invalid category."})

    all_questions = questions_data[category]
    used_by_cat = profile.setdefault("used_by_cat", {})
    last_q_by_cat = profile.setdefault("last_question_by_cat", {})
    used = set(used_by_cat.get(category, []))

    candidates = [q for q in all_questions if q["question"] not in used]

    last_q = last_q_by_cat.get(category)
    if last_q and len(candidates) > 1:
        candidates = [q for q in candidates if q["question"] != last_q] or candidates

    if not candidates:
        used_by_cat[category] = []
        used = set()
        candidates = list(all_questions)

    scored = []
    for q in candidates:
        concept = extract_concept(q["question"])
        scores = profile["concept_scores"].get(concept, [5.0])
        avg_score = sum(scores) / len(scores)
        scored.append((q, avg_score))

    scored.sort(key=lambda x: x[1])
    from random import choice
    k = min(3, len(scored))
    selected = choice(scored[:k])[0]

    used_by_cat.setdefault(category, []).append(selected["question"])
    last_q_by_cat[category] = selected["question"]

    resp = jsonify({"question": selected["question"]})
    resp = make_response(resp)
    resp.set_cookie('user_id', user_id, max_age=60*60*24*30, httponly=True, samesite='Lax')
    return resp


@bp.route("/submit-answer", methods=["POST"])
def submit_answer():
    data = request.get_json(silent=True) or {}
    question = data.get("question")
    answer = data.get("answer")

    if not question or not answer:
        return jsonify({"error": "Missing question or answer."}), 400

    try:
        result = analyze_answer(question, answer)
        if 'error' in result:
            return jsonify(result), 400

        user_id = request.cookies.get('user_id')
        if user_id and user_id in user_profiles:
            profile = user_profiles[user_id]
            concept = extract_concept(question)
            score = result.get("score", 0)
            if isinstance(score, (int, float)) and score > 0:
                profile["concept_scores"][concept].append(float(score))

        return jsonify(result)
    except Exception as e:
        logger.exception("Analyzer failure: %s", e)
        return jsonify({"error": "Analysis service failed."}), 500
