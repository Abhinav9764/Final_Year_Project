import os
import requests
from datetime import datetime

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true"

DEFAULT_SLM_MODELS = [
    "phi3.5:3.8b",
    "llama3.2:3b",
    "llama3.2:1b",
    "smollm2:1.7b",
    "gemma2:2b"
]

def _ollama_available():
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False

def _ollama_chat(model, messages, temperature=0.3, num_predict=512):
    payload = {"model": model, "messages": messages, "options": {"temperature": temperature, "num_predict": num_predict}, "stream": False}
    r = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=20)
    r.raise_for_status()
    return r.json()["message"]["content"]

def _pick_model():
    models_env = os.getenv("SLM_MODELS")
    if models_env:
        return [m.strip() for m in models_env.split(",") if m.strip()]
    return DEFAULT_SLM_MODELS

def generate_slm_response(user_prompt, rag_response, history_pairs=None):
    history_pairs = history_pairs or []

    if MOCK_MODE or not _ollama_available():
        return {"response": f"SLM fallback response based on prompt: {user_prompt}", "model_used": "fallback", "timestamp": datetime.utcnow().isoformat()}

    examples = ""
    for pair in history_pairs[:3]:
        examples += f"\nUser: {pair.get('prompt','')}\nAssistant: {pair.get('response','')}\n"

    system = "You are a concise small language model. Use the RAG context and prior examples."
    user = f"""
RAG CONTEXT:
{rag_response}

PRIOR EXAMPLES:
{examples}

USER PROMPT:
{user_prompt}

Provide a concise, helpful response.
"""

    last_error = None
    for model in _pick_model():
        try:
            content = _ollama_chat(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.3,
                num_predict=512
            )
            return {"response": content, "model_used": model, "timestamp": datetime.utcnow().isoformat()}
        except Exception as e:
            last_error = e

    return {"response": f"SLM generation failed. Prompt: {user_prompt}", "model_used": "error", "error": str(last_error) if last_error else "unknown", "timestamp": datetime.utcnow().isoformat()}
