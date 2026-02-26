"""
brain/extractor.py
==================
NLP keyword extraction from user prompts.

Strategy (in order of preference):
  1. spaCy  — entity/noun-chunk recognition (best quality)
  2. NLTK   — POS-tag-based chunking fallback (Python 3.14 safe)
  3. Regex  — simple alpha-token fallback if NLTK data missing

TF-IDF ranking (scikit-learn) is applied regardless of which NLP
backend is active, giving consistent, ranked output.
"""

from __future__ import annotations

import logging
import re
from typing import TypedDict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public type
# ---------------------------------------------------------------------------

class KeywordBundle(TypedDict):
    primary: list[str]    # High-confidence top-N keywords
    secondary: list[str]  # Remaining ranked keywords
    tags: list[str]       # Single-word tokens from primary (Kaggle-friendly)


# ---------------------------------------------------------------------------
# NLP backend helpers
# ---------------------------------------------------------------------------

def _try_spacy(model_name: str):
    """Load a spaCy model if available; return None on any failure."""
    try:
        import spacy  # noqa: PLC0415
        nlp = spacy.load(model_name)
        logger.debug("spaCy backend active (model: %s).", model_name)
        return nlp
    except Exception as exc:  # noqa: BLE001
        logger.info(
            "spaCy unavailable (%s). Falling back to NLTK backend.", exc
        )
        return None


def _extract_with_spacy(nlp, text: str) -> list[str]:
    """Extract candidates using spaCy named entities + noun chunks."""
    doc = nlp(text)
    candidates: list[str] = []
    for ent in doc.ents:
        phrase = ent.text.lower().strip()
        if len(phrase) > 2 and phrase not in candidates:
            candidates.append(phrase)
    for chunk in doc.noun_chunks:
        phrase = chunk.text.lower().strip()
        if len(phrase) > 2 and phrase not in candidates:
            candidates.append(phrase)
    # Individual non-stop tokens
    for token in doc:
        if not token.is_stop and not token.is_punct and token.is_alpha and len(token.text) > 2:
            word = token.text.lower()
            if word not in candidates:
                candidates.append(word)
    return candidates


def _ensure_nltk_resources() -> bool:
    """Download required NLTK resources; return True on success."""
    try:
        import nltk  # noqa: PLC0415
        for resource in ("punkt", "averaged_perceptron_tagger",
                         "averaged_perceptron_tagger_eng", "stopwords", "punkt_tab"):
            try:
                nltk.data.find(f"tokenizers/{resource}")
            except LookupError:
                try:
                    nltk.data.find(f"taggers/{resource}")
                except LookupError:
                    nltk.download(resource, quiet=True)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("NLTK resource setup failed: %s", exc)
        return False


def _extract_with_nltk(text: str) -> list[str]:
    """Extract noun-phrase candidates using NLTK POS tagging."""
    try:
        import nltk  # noqa: PLC0415
        from nltk.corpus import stopwords  # noqa: PLC0415

        _ensure_nltk_resources()
        stops = set(stopwords.words("english"))

        tokens = nltk.word_tokenize(text)
        tagged = nltk.pos_tag(tokens)

        # Grammar: noun phrases (NP → optional JJ* + NN*)
        grammar = r"""
            NP: {<JJ>*<NN.*>+}
        """
        parser = nltk.RegexpParser(grammar)
        tree = parser.parse(tagged)

        candidates: list[str] = []
        for subtree in tree.subtrees(filter=lambda t: t.label() == "NP"):
            phrase = " ".join(w.lower() for w, _ in subtree.leaves() if w.isalpha())
            if len(phrase) > 2 and phrase not in candidates:
                candidates.append(phrase)

        # Single nouns/adjectives not already captured
        for word, pos in tagged:
            if pos.startswith(("NN", "JJ")) and word.isalpha() and len(word) > 2:
                w = word.lower()
                if w not in stops and w not in candidates:
                    candidates.append(w)

        logger.debug("NLTK extracted %d candidates.", len(candidates))
        return candidates

    except Exception as exc:  # noqa: BLE001
        logger.warning("NLTK extraction failed: %s. Using regex fallback.", exc)
        return _extract_with_regex(text)


def _extract_with_regex(text: str) -> list[str]:
    """Minimal regex-based extraction: alpha tokens longer than 2 chars."""
    STOPWORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "is", "was", "are", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "not", "this", "that",
        "it", "its", "as", "by", "from", "about", "into", "than", "then",
    }
    tokens = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    seen: list[str] = []
    for t in tokens:
        if t not in STOPWORDS and t not in seen:
            seen.append(t)
    return seen


# ---------------------------------------------------------------------------
# TF-IDF ranking
# ---------------------------------------------------------------------------

def _rank_by_tfidf(candidates: list[str], prompt: str, top_n: int) -> list[str]:
    """Rank candidates by TF-IDF cosine similarity against the original prompt."""
    if not candidates:
        return []
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: PLC0415
        from sklearn.metrics.pairwise import cosine_similarity  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415

        corpus = candidates + [prompt]
        vectorizer = TfidfVectorizer(ngram_range=(1, 2))
        matrix = vectorizer.fit_transform(corpus)
        scores = cosine_similarity(matrix[-1], matrix[:-1]).flatten()
        ranked_idx = np.argsort(scores)[::-1]
        return [candidates[i] for i in ranked_idx]

    except Exception as exc:  # noqa: BLE001
        logger.debug("TF-IDF ranking failed (%s). Using original order.", exc)
        return candidates


# ---------------------------------------------------------------------------
# Extractor class
# ---------------------------------------------------------------------------

class KeywordExtractor:
    """
    Extracts and ranks keywords from a free-text prompt.

    Tries spaCy → NLTK → Regex backends in order. TF-IDF ranking
    is always applied on top of whichever backend succeeds.

    Parameters
    ----------
    config : dict
        The ``nlp`` section of config.yaml.
    """

    def __init__(self, config: dict) -> None:
        self._model_name: str = config.get("spacy_model", "en_core_web_sm")
        self._top_n: int = config.get("top_keywords", 5)
        self._nlp = None          # Lazy-loaded on first call
        self._backend: str = "unresolved"

    def _load_backend(self) -> None:
        """Choose the best available NLP backend once."""
        if self._backend != "unresolved":
            return
        nlp = _try_spacy(self._model_name)
        if nlp is not None:
            self._nlp = nlp
            self._backend = "spacy"
        else:
            self._backend = "nltk"
            logger.info("Using NLTK extraction backend.")

    def extract(self, prompt: str) -> KeywordBundle:
        """
        Extract a structured bundle of keywords from *prompt*.

        Parameters
        ----------
        prompt : str
            Raw user research prompt.

        Returns
        -------
        KeywordBundle
            ``primary``   — top keywords (≤ ``top_keywords`` from config).
            ``secondary`` — remaining ranked keywords.
            ``tags``      — single-word entries from primary.

        Raises
        ------
        ValueError
            If the prompt is empty.
        RuntimeError
            On unexpected extraction failure.
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt must be a non-empty string.")

        try:
            self._load_backend()

            if self._backend == "spacy" and self._nlp is not None:
                candidates = _extract_with_spacy(self._nlp, prompt)
            else:
                candidates = _extract_with_nltk(prompt)

            if not candidates:
                logger.warning("No candidates found; falling back to regex.")
                candidates = _extract_with_regex(prompt)

            ranked = _rank_by_tfidf(candidates, prompt, self._top_n)
            primary = ranked[: self._top_n]
            secondary = ranked[self._top_n :]
            tags = [kw for kw in primary if " " not in kw]

            bundle: KeywordBundle = {
                "primary": primary,
                "secondary": secondary,
                "tags": tags,
            }

            logger.info(
                "Keywords [%s backend] — primary: %s",
                self._backend,
                primary,
            )
            return bundle

        except ValueError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error during keyword extraction.")
            raise RuntimeError(
                f"Keyword extraction failed: {exc}"
            ) from exc
