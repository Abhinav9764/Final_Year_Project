"""
core/router.py — NLP Intent Router
====================================
Classifies a user's natural-language prompt into one of two routes:
  - "chatbot"  : the user wants a conversational AI / knowledge-base bot
  - "ml"       : the user wants a predictive model / regression / classification

Strategy:
  1. Keyword scoring   — fast, deterministic baseline
  2. Sentence embedding cosine similarity — more nuanced if keywords tie
  3. Returns a RouteDecision dataclass with mode, confidence, and keywords
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import List

log = logging.getLogger(__name__)

# ── Keyword Lexicons ──────────────────────────────────────────────────────────
CHATBOT_KEYWORDS = [
    "chatbot", "chat", "conversation", "assistant", "talk", "answer",
    "faq", "support", "knowledge base", "question", "ask", "discuss",
    "explain", "helpdesk", "dialogue", "nlp", "language model", "rag",
    "information", "research", "web search", "scrape", "articles",
    "document", "summarise", "summarize", "wiki",
]

ML_KEYWORDS = [
    "predict", "prediction", "forecast", "classify", "classification",
    "regression", "neural network", "random forest", "xgboost", "model",
    "train", "training", "machine learning", "ml", "deep learning",
    "dataset", "csv", "feature", "accuracy", "loss", "sagemaker",
    "autopilot", "inference", "label", "target", "score",
    "churn", "price", "risk", "sentiment", "anomaly", "detection",
]

RECOMMENDATION_KEYWORDS = [
    "recommend", "recommendation", "recommender", "suggest", "suggestion",
    "top 5", "top 10", "top n", "item", "user-item", "collaborative filtering",
    "content-based", "similar", "similarity", "match", "matching", "discover"
]


@dataclass
class RouteDecision:
    mode:       str             # "chatbot" | "ml" | "recommendation"
    confidence: float           # 0.0 – 1.0
    keywords:   List[str] = field(default_factory=list)
    raw_scores: dict = field(default_factory=dict)


class Router:
    """Classifies user intent using keyword scoring + optional embedding fallback."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._embedder = None   # lazy-loaded

    # ── Public API ────────────────────────────────────────────────────────────
    def classify(self, prompt: str) -> RouteDecision:
        tokens = self._tokenize(prompt)
        cb_score = self._score(tokens, CHATBOT_KEYWORDS)
        ml_score = self._score(tokens, ML_KEYWORDS)
        rec_score = self._score(tokens, RECOMMENDATION_KEYWORDS)

        log.debug("Keyword scores — chatbot=%.2f  ml=%.2f  recommendation=%.2f", cb_score, ml_score, rec_score)

        total = cb_score + ml_score + rec_score

        if total == 0:
            # No direct keyword matches → fall back to embedding similarity
            return self._embedding_classify(prompt)

        scores = {"chatbot": cb_score, "ml": ml_score, "recommendation": rec_score}
        mode = max(scores, key=scores.get)
        confidence = scores[mode] / total

        keywords = self._extract_keywords(tokens, mode)

        decision = RouteDecision(
            mode=mode,
            confidence=round(confidence, 3),
            keywords=keywords,
            raw_scores=scores,
        )
        log.info("Route → %s (conf=%.2f) | keywords=%s", mode, confidence, keywords)
        return decision

    # ── Internal Helpers ──────────────────────────────────────────────────────
    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"[a-zA-Z0-9]+", text.lower())

    @staticmethod
    def _score(tokens: List[str], lexicon: List[str]) -> float:
        """Count how many lexicon phrases appear (multi-word aware)."""
        joined = " ".join(tokens)
        score = 0.0
        for phrase in lexicon:
            if phrase in joined:
                # multi-word phrases count more
                score += len(phrase.split())
        return score

    @staticmethod
    def _extract_keywords(tokens: List[str], mode: str) -> List[str]:
        """Return the matched keywords for downstream use in search queries."""
        if mode == "chatbot":
            lexicon = CHATBOT_KEYWORDS
        elif mode == "recommendation":
            lexicon = RECOMMENDATION_KEYWORDS
        else:
            lexicon = ML_KEYWORDS
            
        joined  = " ".join(tokens)
        found   = [kw for kw in lexicon if kw in joined]
        # De-duplicate and return meaningful ones
        seen, result = set(), []
        for kw in found:
            kw_clean = kw.strip()
            if kw_clean not in seen:
                seen.add(kw_clean)
                result.append(kw_clean)
        return result[:10]

    def _embedding_classify(self, prompt: str) -> RouteDecision:
        """
        Fallback: compare prompt embedding to prototype sentences using
        sentence-transformers cosine similarity.
        """
        try:
            from sentence_transformers import SentenceTransformer, util  # type: ignore

            if self._embedder is None:
                model_name = self.cfg.get("vector_store", {}).get("embedding_model", "all-MiniLM-L6-v2")
                log.info("Loading sentence-transformer %s for routing fallback.", model_name)
                self._embedder = SentenceTransformer(model_name)

            prototypes = {
                "chatbot": "Build a conversational AI chatbot that answers user questions.",
                "ml":      "Build a machine learning model to make predictions from tabular data.",
                "recommendation": "Build a recommendation system to suggest top n items for users based on similarity.",
            }
            prompt_emb = self._embedder.encode(prompt, convert_to_tensor=True)
            scores = {
                mode: float(util.cos_sim(prompt_emb, self._embedder.encode(ref, convert_to_tensor=True)))
                for mode, ref in prototypes.items()
            }
            mode = max(scores, key=scores.get)
            total = sum(scores.values())
            confidence = scores[mode] / total if total else 0.5
            log.info("Embedding fallback route → %s (conf=%.2f)", mode, confidence)
            return RouteDecision(mode=mode, confidence=round(confidence, 3), raw_scores=scores)

        except ImportError:
            log.warning("sentence-transformers not available; defaulting to 'chatbot'.")
            return RouteDecision(mode="chatbot", confidence=0.5)
