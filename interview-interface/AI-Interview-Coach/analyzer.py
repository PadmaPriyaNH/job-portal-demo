from flask import Flask, request, jsonify
from sentence_transformers import SentenceTransformer, util
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)

print("Loading AI model...")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("Model loaded.")

with open(os.path.join(BASE_DIR, 'questions.json'), 'r', encoding='utf-8') as f:
    questions_data = json.load(f)

def find_ideal_answer(question_text):
    for category in questions_data.values():
        for q in category:
            if q["question"] == question_text:
                return q.get("ideal_answer", "")
    return ""

def contains_key_concepts(user_answer, ideal_answer):
    key_terms = set()
    lower_ideal = ideal_answer.lower()
    
    if "hash table" in lower_ideal:
        key_terms.update(["hash", "bucket", "collision", "o(1)"])
    elif "time complexity" in lower_ideal:
        key_terms.update(["o(", "complexity", "runtime", "scale"])
    elif "tcp" in lower_ideal or "udp" in lower_ideal:
        key_terms.update(["tcp", "udp", "reliable", "connection", "speed"])
    elif "recursion" in lower_ideal:
        key_terms.update(["base case", "stack", "function calls", "iterative"])
    elif "closure" in lower_ideal:
        key_terms.update(["enclosing scope", "private", "function factory"])
    elif "garbage collection" in lower_ideal:
        key_terms.update(["reference counting", "memory", "cyclic", "free"])
    elif "api gateway" in lower_ideal:
        key_terms.update(["microservices", "routing", "authentication", "entry point"])
    elif "cap theorem" in lower_ideal:
        key_terms.update(["consistency", "availability", "partition tolerance"])
    elif "authentication" in lower_ideal:
        key_terms.update(["identity", "login", "authorization", "permissions"])
    elif "global state" in lower_ideal:
        key_terms.update(["mutable", "bug", "test", "pure function"])
    elif "lazy loading" in lower_ideal:
        key_terms.update(["delay", "performance", "memory", "initialize"])
    elif "https" in lower_ideal:
        key_terms.update(["tls", "ssl", "encrypt", "certificate", "man-in-the-middle"])
    elif "process" in lower_ideal and "thread" in lower_ideal:
        key_terms.update(["memory space", "isolation", "lightweight", "race condition"])
    elif "sql query" in lower_ideal:
        key_terms.update(["explain", "index", "slow query", "profiler"])
    else:
        key_terms = set(re.findall(r'\b\w{4,}\b', lower_ideal))
    
    user_lower = user_answer.lower()
    matched = [term for term in key_terms if term in user_lower]
    return matched, key_terms

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    question = data.get('question', '').strip()
    answer = data.get('answer', '').strip()

    if not question or not answer:
        return jsonify({"error": "Question and answer are required."}), 400

    ideal = find_ideal_answer(question)
    if not ideal:
        return jsonify({"score": 0, "feedback": "No reference answer found for this question."})

    word_count = len(answer.split())
    sentence_count = len([s for s in re.split(r'[.!?]+', answer) if s.strip()])
    if word_count < 25 or sentence_count < 2:
        return jsonify({
            "score": 1.5,
            "feedback": "⚠️ Your answer is too brief. Aim for at least 2-3 sentences (≈25+ words) covering core ideas, examples, and trade-offs."
        })

    embeddings = model.encode([answer, ideal, question], convert_to_tensor=True)
    similarity = util.cos_sim(embeddings[0], embeddings[1]).item()
    aq_sim = util.cos_sim(embeddings[0], embeddings[2]).item()
    if similarity < 0.20:
        return jsonify({
            "score": 2.0,
            "feedback": "❌ Your response appears off-topic. Please re-read the question and address it directly with relevant details."
        })

    # Detect copying/echoing the question
    answer_tokens = set(re.findall(r'\b\w{3,}\b', answer.lower()))
    question_tokens = set(re.findall(r'\b\w{3,}\b', question.lower()))
    jaccard = (len(answer_tokens & question_tokens) / len(answer_tokens | question_tokens)) if (answer_tokens | question_tokens) else 0.0
    if aq_sim > 0.85 or jaccard > 0.6:
        return jsonify({
            "score": 1.8,
            "feedback": "❌ Your answer closely mirrors the question. Provide an explanatory response with definitions, key concepts, and examples."
        })

    matched_concepts, all_concepts = contains_key_concepts(answer, ideal)
    concept_coverage = len(matched_concepts) / len(all_concepts) if all_concepts else 0

    # Normalize similarity to reduce inflated scores for generic answers
    norm_sim = max(0.0, (similarity - 0.30) / 0.70)
    base_score = norm_sim * 6.0
    concept_score = concept_coverage * 4.0

    # Small bonus for structure/clarity cues
    structure_bonus = 0.5 if re.search(r"\b(for example|e\.g\.|such as|for instance)\b", answer.lower()) else 0.0

    total_score = min(round(base_score + concept_score + structure_bonus, 1), 10.0)

    missing = [c for c in list(all_concepts)[:3] if c not in matched_concepts]
    if total_score >= 8.5:
        feedback = "✅ **Excellent!** You demonstrated deep understanding with clear examples and key concepts."
    elif total_score >= 7.0:
        feedback = "👍 **Strong answer!** You covered the core ideas well. To improve: add more specific details or real-world context."
    elif total_score >= 5.0:
        feedback = f"💡 **Good start!** You're on the right track. Consider discussing: {', '.join(missing[:2])}."
    elif total_score >= 3.0:
        feedback = f"🔧 **Needs work.** Your answer misses key concepts like: {', '.join(missing[:3])}. Review the topic and try again."
    else:
        feedback = "📚 **Study recommended.** This response doesn't reflect understanding of the core concepts. Please review fundamentals."

    if total_score < 5.0:
        feedback += " Tip: Break the concept into smaller parts and explain each step."

    return jsonify({
        "score": total_score,
        "feedback": feedback,
        "matched_concepts": matched_concepts,
        "missing_concepts": missing,
        "concept_coverage": round(concept_coverage, 2)
    })

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)