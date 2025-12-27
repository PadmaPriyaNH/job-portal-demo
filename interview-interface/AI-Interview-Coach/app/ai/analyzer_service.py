import os
import re
import json
import threading
from typing import Dict, List, Tuple

try:
    from sentence_transformers import SentenceTransformer, util
except Exception as e:
    SentenceTransformer = None  # type: ignore
    util = None  # type: ignore


_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_DIR = os.path.dirname(_BASE_DIR)

_MODEL = None
_MODEL_LOCK = threading.Lock()


def _get_model():
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    with _MODEL_LOCK:
        if _MODEL is None:
            model_name = os.getenv("MODEL_NAME", "all-MiniLM-L6-v2")
            if SentenceTransformer is None:
                raise RuntimeError(
                    "sentence-transformers is not available. Ensure dependencies are installed."
                )
            _MODEL = SentenceTransformer(model_name)
    return _MODEL


def _load_questions() -> Dict[str, List[Dict[str, str]]]:
    path = os.path.join(_PROJECT_DIR, "questions.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _find_ideal_answer(question_text: str, questions_data: Dict[str, List[Dict[str, str]]]) -> str:
    for category in questions_data.values():
        for q in category:
            if q.get("question") == question_text:
                return q.get("ideal_answer", "")
    return ""


def _contains_key_concepts(user_answer: str, ideal_answer: str) -> Tuple[List[str], List[str]]:
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
        key_terms = set(re.findall(r"\b\w{4,}\b", lower_ideal))

    user_lower = user_answer.lower()
    matched = [term for term in key_terms if term in user_lower]
    return matched, list(key_terms)


def analyze_answer(question: str, answer: str) -> Dict:
    """Analyze an answer against an ideal answer and return scoring details."""
    if not question or not answer:
        return {"error": "Question and answer are required."}

    questions_data = _load_questions()
    ideal = _find_ideal_answer(question, questions_data)
    if not ideal:
        return {"score": 0, "feedback": "No reference answer found for this question."}

    word_count = len(answer.split())
    sentence_count = len([s for s in re.split(r"[.!?]+", answer) if s.strip()])
    if word_count < 25 or sentence_count < 2:
        return {
            "score": 1.5,
            "feedback": "Your answer is too brief. Aim for at least 2-3 sentences (≈25+ words) covering core ideas, examples, and trade-offs.",
        }

    model = _get_model()
    embeddings = model.encode([answer, ideal, question], convert_to_tensor=True)
    try:
        sim_ai = float(util.cos_sim(embeddings[0], embeddings[1]).item())
        sim_aq = float(util.cos_sim(embeddings[0], embeddings[2]).item())
    except Exception:
        sim_ai = 0.0
        sim_aq = 0.0

    if sim_ai < 0.20:
        return {
            "score": 2.0,
            "feedback": "Your response appears off-topic. Re-read the question and address it directly with relevant details.",
        }

    # Detect copying/echoing the question
    answer_tokens = set(re.findall(r"\b\w{3,}\b", answer.lower()))
    question_tokens = set(re.findall(r"\b\w{3,}\b", question.lower()))
    jaccard = (
        len(answer_tokens & question_tokens) / len(answer_tokens | question_tokens)
        if (answer_tokens | question_tokens)
        else 0.0
    )
    if sim_aq > 0.85 or jaccard > 0.6:
        return {
            "score": 1.8,
            "feedback": "Your answer closely mirrors the question. Provide an explanatory response with definitions, key concepts, and examples.",
        }

    matched, all_terms = _contains_key_concepts(answer, ideal)
    coverage = len(matched) / len(all_terms) if all_terms else 0

    norm_sim = max(0.0, (sim_ai - 0.30) / 0.70)
    base_score = norm_sim * 6.0
    concept_score = coverage * 4.0
    structure_bonus = 0.5 if re.search(r"\b(for example|e\.g\.|such as|for instance)\b", answer.lower()) else 0.0
    total_score = min(round(base_score + concept_score + structure_bonus, 1), 10.0)

    missing = [c for c in list(all_terms)[:3] if c not in matched]
    if total_score >= 8.5:
        feedback = "Excellent! You demonstrated deep understanding with clear examples and key concepts."
    elif total_score >= 7.0:
        feedback = "Strong answer! You covered the core ideas well. To improve: add more specific details or real-world context."
    elif total_score >= 5.0:
        feedback = f"Good start! You're on the right track. Consider discussing: {', '.join(missing[:2])}."
    elif total_score >= 3.0:
        feedback = f"Needs work. Your answer misses key concepts like: {', '.join(missing[:3])}. Review the topic and try again."
    else:
        feedback = "Study recommended. This response doesn't reflect understanding of the core concepts. Please review fundamentals."

    if total_score < 5.0:
        feedback += " Tip: Break the concept into smaller parts and explain each step."

    return {
        "score": total_score,
        "feedback": feedback,
        "matched_concepts": matched,
        "missing_concepts": missing,
        "concept_coverage": round(coverage, 2),
    }
