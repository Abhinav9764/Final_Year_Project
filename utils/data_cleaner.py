"""
utils/data_cleaner.py
=====================
Pre-processing utilities for raw collected data.

Provides:
  - ``clean_text``  — strips HTML noise, normalises whitespace, removes stopwords.
  - ``clean_csv``  — drops nulls, normalises column names, saves to processed/.
  - ``DataVerifier`` — verifies collected data quality BEFORE the RL reward
    is computed, ensuring the agent only learns from genuine information.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Text Cleaning
# ---------------------------------------------------------------------------

def _get_stopwords() -> set[str]:
    """Return NLTK English stopwords, or a small built-in set on failure."""
    try:
        from nltk.corpus import stopwords  # noqa: PLC0415
        import nltk  # noqa: PLC0415

        try:
            return set(stopwords.words("english"))
        except LookupError:
            nltk.download("stopwords", quiet=True)
            return set(stopwords.words("english"))
    except ImportError:
        logger.warning("NLTK not available — using built-in stopword set.")
        return {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "is", "was", "are", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "not", "this", "that",
        }


def clean_text(raw_text: str, *, remove_stopwords: bool = False) -> str:
    """
    Clean raw text extracted from web pages or API responses.

    Steps:
      1. Unicode normalisation (NFKD → ASCII)
      2. Strip HTML tags
      3. Collapse whitespace
      4. Optionally remove stopwords

    Parameters
    ----------
    raw_text : str
        Unprocessed text string.
    remove_stopwords : bool
        If True, removes common English stopwords.

    Returns
    -------
    str
        Cleaned text string (may be empty if input contained no content).

    Raises
    ------
    TypeError
        If *raw_text* is not a string.
    """
    if not isinstance(raw_text, str):
        raise TypeError(f"clean_text expects str, got {type(raw_text).__name__}")

    # Unicode normalise
    text = unicodedata.normalize("NFKD", raw_text)
    text = text.encode("ascii", errors="ignore").decode("ascii")

    # Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Collapse whitespace / control chars
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()

    if remove_stopwords:
        stops = _get_stopwords()
        words = text.split()
        text = " ".join(w for w in words if w.lower() not in stops)

    return text


# ---------------------------------------------------------------------------
# CSV Cleaning
# ---------------------------------------------------------------------------

def clean_csv(filepath: str | Path, output_dir: str | Path) -> Optional[Path]:
    """
    Load a CSV, clean it, and save to *output_dir*.

    Cleaning steps:
      - Drop fully empty rows and columns
      - Strip whitespace from column names and string cell values
      - Normalise column names to lowercase with underscores
      - Drop duplicate rows

    Parameters
    ----------
    filepath : str | Path
        Path to the raw CSV file.
    output_dir : str | Path
        Directory where the cleaned file is saved.

    Returns
    -------
    Path | None
        Path to the saved cleaned file, or None if processing failed.

    Raises
    ------
    FileNotFoundError
        If *filepath* does not exist.
    """
    filepath = Path(filepath)
    output_dir = Path(output_dir)

    if not filepath.exists():
        raise FileNotFoundError(f"CSV file not found: {filepath}")

    try:
        import pandas as pd  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "pandas is required for CSV cleaning. Run: pip install pandas"
        ) from exc

    try:
        df = pd.read_csv(filepath)
    except Exception as exc:
        logger.error("Failed to read CSV '%s': %s", filepath, exc)
        return None

    original_shape = df.shape

    # Drop fully empty rows/cols
    df.dropna(how="all", inplace=True)
    df.dropna(axis=1, how="all", inplace=True)

    # Normalise column names
    df.columns = [
        re.sub(r"\s+", "_", col.strip().lower()) for col in df.columns
    ]

    # Strip string values
    str_cols = df.select_dtypes(include="object").columns
    df[str_cols] = df[str_cols].apply(lambda col: col.str.strip())

    # Drop duplicate rows
    df.drop_duplicates(inplace=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / filepath.name

    try:
        df.to_csv(out_path, index=False)
        logger.info(
            "CSV cleaned %s → %s  [%d×%d → %d×%d]",
            filepath.name,
            out_path,
            *original_shape,
            *df.shape,
        )
        return out_path
    except OSError as exc:
        logger.error("Could not save cleaned CSV to '%s': %s", out_path, exc)
        return None


# ---------------------------------------------------------------------------
# Data Verifier  (called BEFORE reward computation)
# ---------------------------------------------------------------------------

class DataVerifier:
    """
    Verifies that collected data meets minimum quality thresholds BEFORE
    the RL environment computes its reward.

    This prevents the Q-learning agent from learning from low-quality,
    irrelevant, or empty data, keeping the reward signal honest.

    Parameters
    ----------
    config : dict
        The ``verification`` section of config.yaml.
    """

    def __init__(self, config: dict) -> None:
        self._min_length: int = config.get("min_text_length", 100)
        self._min_coverage: float = config.get("min_keyword_coverage", 0.2)
        self._min_similarity: float = config.get("min_cosine_similarity", 0.1)

        if not (0.0 <= self._min_coverage <= 1.0):
            raise ValueError(
                f"min_keyword_coverage must be in [0, 1], "
                f"got {self._min_coverage}"
            )

    def verify(
        self,
        text: str,
        keywords: list[str],
    ) -> tuple[bool, dict[str, object]]:
        """
        Run all quality checks on collected *text*.

        Checks
        ------
        1. **Length check** — text must have ≥ ``min_text_length`` characters.
        2. **Keyword coverage** — fraction of keywords appearing in text
           must be ≥ ``min_keyword_coverage``.
        3. **Cosine similarity** — TF-IDF similarity between keyword string
           and text must be ≥ ``min_cosine_similarity``.

        Parameters
        ----------
        text : str
            Collected and cleaned text to verify.
        keywords : list[str]
            Primary keywords used for the search.

        Returns
        -------
        (passed: bool, report: dict)
            ``passed`` — True only when ALL checks pass.
            ``report`` — Detailed per-check results for logging / debugging.
        """
        report: dict[str, object] = {}
        passed_flags: list[bool] = []

        # --- Check 1: Length ---
        length_ok = len(text) >= self._min_length
        report["length"] = {
            "value":     len(text),
            "threshold": self._min_length,
            "passed":    length_ok,
        }
        passed_flags.append(length_ok)

        if not length_ok:
            logger.debug(
                "Verification FAIL (length): %d < %d chars",
                len(text),
                self._min_length,
            )

        # --- Check 2: Keyword Coverage ---
        text_lower = text.lower()
        hits = sum(1 for kw in keywords if kw.lower() in text_lower)
        coverage = hits / len(keywords) if keywords else 0.0
        coverage_ok = coverage >= self._min_coverage
        report["keyword_coverage"] = {
            "value":     round(coverage, 4),
            "threshold": self._min_coverage,
            "passed":    coverage_ok,
        }
        passed_flags.append(coverage_ok)

        if not coverage_ok:
            logger.debug(
                "Verification FAIL (coverage): %.2f < %.2f",
                coverage,
                self._min_coverage,
            )

        # --- Check 3: TF-IDF Cosine Similarity ---
        similarity = self._compute_similarity(text, keywords)
        sim_ok = similarity >= self._min_similarity
        report["cosine_similarity"] = {
            "value":     round(similarity, 4),
            "threshold": self._min_similarity,
            "passed":    sim_ok,
        }
        passed_flags.append(sim_ok)

        if not sim_ok:
            logger.debug(
                "Verification FAIL (similarity): %.4f < %.4f",
                similarity,
                self._min_similarity,
            )

        overall = all(passed_flags)
        report["overall_passed"] = overall

        level = logger.info if overall else logger.warning
        level(
            "Data verification %s | length=%d, coverage=%.2f, similarity=%.4f",
            "PASSED ✓" if overall else "FAILED ✗",
            len(text),
            coverage,
            similarity,
        )
        return overall, report

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_similarity(text: str, keywords: list[str]) -> float:
        """TF-IDF cosine similarity between keyword string and text."""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: PLC0415
            from sklearn.metrics.pairwise import cosine_similarity  # noqa: PLC0415

            keyword_str = " ".join(keywords)
            if not keyword_str.strip() or not text.strip():
                return 0.0

            vectorizer = TfidfVectorizer()
            matrix = vectorizer.fit_transform([keyword_str, text])
            score: float = cosine_similarity(matrix[0], matrix[1])[0][0]
            return float(score)

        except Exception as exc:  # noqa: BLE001
            logger.debug("Cosine similarity computation failed: %s", exc)
            return 0.0
