from flask import Flask, render_template, request, jsonify
import json
import random
import requests
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

# URL of System B (analysis server)
SYSTEM_B_URL = os.getenv("SYSTEM_B_URL", "http://127.0.0.1:5000/analyze")

# Load questions from JSON (path-safe)
with open(os.path.join(BASE_DIR, "questions.json"), "r", encoding="utf-8") as file:
    questions_data = json.load(file)

# Keep track of current question index per session (for simplicity, we'll use a global)
current_question_index = {}
used_questions = {}

# Welcome page route
@app.route("/")
def welcome():
    print("Serving welcome page...")
    return render_template("welcome.html")

# Interview page route
@app.route("/interview")
def interview():
    categories = list(questions_data.keys())
    return render_template("index.html", categories=categories)

@app.route('/thankyou')
def thank_you():
    return render_template('thankyou.html')

@app.route("/get-question", methods=["POST"])
def get_question():
    category = request.json.get("category")

    if category not in used_questions:
        used_questions[category] = []

    remaining_questions = [q for q in questions_data[category] if q["question"] not in used_questions[category]]

    if not remaining_questions:
        return jsonify({"message": "No more questions in this category."})

    question = random.choice(remaining_questions)
    used_questions[category].append(question["question"])
    return jsonify({"question": question["question"], "keywords": question["keywords"]})

@app.route("/submit-answer", methods=["POST"])
def submit_answer():
    data = request.json
    question = data.get("question")
    answer = data.get("answer")
    keywords = data.get("keywords")

    payload = {
        "question": question,
        "answer": answer,
        "keywords": keywords
    }

    try:
        response = requests.post(SYSTEM_B_URL, json=payload)
        result = response.json()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": "System B not reachable", "details": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False)