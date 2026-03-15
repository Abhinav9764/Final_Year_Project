import re
from collections import Counter

def clean_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def detect_ml_task(prompt: str) -> str:
    prompt_lower = prompt.lower()
    task_patterns = {
        "classification": ["classify", "classification", "churn", "predict class"],
        "regression": ["regression", "predict value", "forecast", "price"],
        "clustering": ["cluster", "segmentation", "group"],
        "nlp": ["text", "sentiment", "language", "summarize"]
    }
    for task, patterns in task_patterns.items():
        if any(p in prompt_lower for p in patterns):
            return task
    return "classification"

def extract_keywords(prompt: str, top_n: int = 8):
    cleaned = clean_text(prompt)
    words = re.findall(r"\b[a-z]{3,}\b", cleaned)
    stops = {"the","and","for","with","build","app","using","model","prediction"}
    filtered = [w for w in words if w not in stops]
    return [w for w, _ in Counter(filtered).most_common(top_n)]

def analyze_prompt(prompt: str):
    cleaned = clean_text(prompt)
    keywords = extract_keywords(prompt)
    ml_task = detect_ml_task(prompt)
    return {
        "original_prompt": prompt,
        "cleaned_prompt": cleaned,
        "keywords": keywords,
        "ml_task": ml_task
    }
