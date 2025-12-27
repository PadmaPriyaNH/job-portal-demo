import spacy
from flask import Flask, request, jsonify
import json
import random
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)

# Try loading a medium model, fallback to small if unavailable
try:
    nlp = spacy.load('en_core_web_md')
except Exception:
    try:
        nlp = spacy.load('en_core_web_sm')
    except Exception:
        nlp = spacy.blank('en')

# Load questions with keywords
with open(os.path.join(BASE_DIR, 'questions.json'), 'r', encoding='utf-8') as file:
    questions_data = json.load(file)

# Feedback messages categorized by score range
feedback_messages = {
    "1-2": [
        "Poor attempt. You need to cover more relevant points.",
        "Your response is lacking. Please try to understand the question better.",
        "Barely any relevant points covered. Revise the topic thoroughly."
    ],
    "2-4": [
        "Below average. You need to include more important aspects.",
        "You covered some points but missed many critical ones.",
        "Try to provide more detailed and relevant responses."
    ],
    "5-7": [
        "Average performance. You have addressed some key points, but more is needed.",
        "Decent attempt, but there’s room for improvement.",
        "You mentioned several relevant points, but try to cover more aspects."
    ],
    "7-8": [
        "Good job! You covered most of the important points but can improve further.",
        "Well done! Try to add a bit more detail next time.",
        "Nice attempt! You addressed the core aspects well."
    ],
    "8-9": [
        "Great work! You’ve covered almost everything well.",
        "Impressive! Just a bit more effort to achieve perfection.",
        "Very good! Just a little more detail would be excellent."
    ],
    "9-10": [
        "Excellent! You provided a thorough and well-rounded response.",
        "Outstanding performance! You covered all key points effectively.",
        "Perfect! You have addressed everything accurately and comprehensively."
    ]
}

# Function to analyze the user's answer based on keywords
def analyze_answer(question, answer):
    doc = nlp(answer)
    keywords = []

    # Find the corresponding question and extract keywords
    for category in questions_data.values():
        for item in category:
            if item["question"] == question:
                keywords = item["keywords"]
                break

    if not keywords:
        return {"score": 0, "feedback": "No keywords found for this question."}

    matched_keywords = [keyword for keyword in keywords if keyword.lower() in answer.lower()]
    match_score = len(matched_keywords) / len(keywords)
    score = round(match_score * 10, 2)

    # Select random feedback based on score range
    if score >= 9:
        feedback = random.choice(feedback_messages["9-10"])
    elif 8 <= score < 9:
        feedback = random.choice(feedback_messages["8-9"])
    elif 7 <= score < 8:
        feedback = random.choice(feedback_messages["7-8"])
    elif 5 <= score < 7:
        feedback = random.choice(feedback_messages["5-7"])
    elif 2 <= score < 5:
        feedback = random.choice(feedback_messages["2-4"])
    else:
        feedback = random.choice(feedback_messages["1-2"])

    return {"score": score, "feedback": feedback}


@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    question = data.get('question')
    answer = data.get('answer')

    if not question or not answer:
        return jsonify({"error": "Invalid input."}), 400

    result = analyze_answer(question, answer)
    return jsonify(result)


if __name__ == '__main__':
    # Bind internally; only system_a should access this service in the same dyno
    app.run(host='127.0.0.1', port=5000, debug=False)