import re

def classify_intent(prompt: str) -> dict:
    """Classify the user prompt into a generation mode and extract hints.

    Returns a dict with keys:
        - mode: "ml" or "chatbot"
        - features: list of feature names (optional, empty list if not applicable)
        - target_column: inferred target column name (optional)
    """
    prompt_lower = prompt.lower()
    # Simple keyword based rules
    ml_keywords = ["predict", "forecast", "regression", "classification", "model", "train", "ml", "machine learning"]
    chatbot_keywords = ["chat", "assistant", "conversation", "dialog", "chatbot", "talk"]
    mode = "ml" if any(k in prompt_lower for k in ml_keywords) else "chatbot"
    # Extract potential target column by looking for "predict <column>" patterns
    target_column = None
    match = re.search(r"predict\s+(\w+)", prompt_lower)
    if match:
        target_column = match.group(1)
    # Dummy feature extraction: look for words after "features" or "columns"
    features = []
    feat_match = re.search(r"features?\s*[:=]\s*([\w,\s]+)", prompt, re.IGNORECASE)
    if feat_match:
        feats = feat_match.group(1)
        features = [f.strip() for f in feats.split(',') if f.strip()]
    return {"mode": mode, "features": features, "target_column": target_column or ""}
