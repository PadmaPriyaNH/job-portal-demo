import os
import re
from typing import List

# Minimal stopword list to extract key concept words from questions
STOPWORDS: List[str] = [
    'what', 'why', 'how', 'when', 'where', 'who', 'whom', 'is', 'are', 'the', 'a', 'an',
    'and', 'or', 'to', 'of', 'in', 'on', 'for', 'with', 'does', 'do', 'you', 'your',
    'explain', 'describe', 'difference', 'between', 'give', 'example', 'examples',
    'tell', 'me', 'about', 'that', 'this', 'it', 'be', 'as', 'at', 'by', 'from',
]


def extract_concept(question_text: str) -> str:
    """Extract a simple concept keyword from a question string.

    - Lowercases and strips punctuation
    - Filters common stopwords and short tokens
    - Returns the first remaining token or a safe fallback
    """
    words = re.sub(r"[^a-zA-Z0-9\s]", " ", question_text.lower()).split()
    filtered = [w for w in words if w not in STOPWORDS and len(w) >= 3]
    return filtered[0] if filtered else (words[0] if words else "general")
