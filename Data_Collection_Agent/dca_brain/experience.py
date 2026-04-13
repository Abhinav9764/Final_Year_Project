"""
Data_Collection_Agent/brain/experience.py
==========================================
Persistent experience memory for the self-learning data collection agent.

The agent records every successful collection run and uses that knowledge
to instantly answer future prompts that are semantically similar — without
re-searching Kaggle/OpenML/UCI from scratch.

Schema (experience_memory.json):
[
  {
    "timestamp":    "2026-04-03T10:06:00",
    "job_id":       "7cd5d1a0",
    "intent":       "ml_model",
    "task_type":    "regression",
    "domain":       "real estate",
    "keywords":     ["rent", "housing"],
    "input_params": ["location", "bhk"],
    "target_param": "price",
    "provider":     "kaggle",
    "dataset_ref":  "iamsouravbanerjee/house-rent-prediction-dataset",
    "row_count":    2930,
    "columns":      ["city", "bhk", "rent", ...],
    "local_path":   "data/raw/...",
    "score":        0.812,
    "use_count":    3
  },
  ...
]

Usage:
    from dca_brain.experience import ExperienceMemory

    mem = ExperienceMemory(config)
    hit = mem.query(spec)                       # None or entry dict
    if hit:
        # Re-use cached dataset path directly
        pass
    else:
        # Search normally, then:
        mem.record(spec, provider, dataset_ref, local_path, row_count, columns, score)
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Minimum similarity threshold to reuse a cached dataset
_MATCH_THRESHOLD = 0.60


class ExperienceMemory:
    """
    Persistent JSON-backed database of successful data collection runs.

    The memory matches on (domain + task_type + intent) with a token-overlap
    distance, keeping it fast and dependency-free.
    """

    def __init__(self, config: dict) -> None:
        storage_cfg = config.get("storage", {})
        db_path_str = storage_cfg.get(
            "experience_db", "Data_Collection_Agent/dca_brain/experience_memory.json"
        )
        self._db_path = Path(db_path_str)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._min_rows = int(config.get("collection", {}).get("min_row_threshold", 500))
        self._entries: list[dict] = self._load()

    # ── Public API ─────────────────────────────────────────────────────────────

    def query(self, spec: dict) -> dict | None:
        """
        Search memory for a past run whose spec closely matches the current spec.

        Returns the best matching entry (dict) if similarity >= threshold,
        else None.  Only entries whose cached local_path still exists and has
        enough rows are considered valid.
        """
        if not self._entries:
            return None

        best_entry: dict | None = None
        best_score: float = 0.0

        for entry in self._entries:
            score = self._similarity(spec, entry)
            if score > best_score:
                best_score = score
                best_entry = entry

        if best_score < _MATCH_THRESHOLD or best_entry is None:
            logger.debug(
                "ExperienceMemory: no match found (best=%.2f < threshold=%.2f)",
                best_score, _MATCH_THRESHOLD,
            )
            return None

        # Validate cached path still exists
        local_path = best_entry.get("local_path", "")
        if not local_path or not Path(local_path).exists():
            logger.info(
                "ExperienceMemory: cached path no longer exists (%s) — ignoring hit",
                local_path,
            )
            return None

        # Validate row count
        if best_entry.get("row_count", 0) < self._min_rows:
            logger.info(
                "ExperienceMemory: cached dataset too small (%d rows) — ignoring hit",
                best_entry.get("row_count", 0),
            )
            return None

        logger.info(
            "ExperienceMemory: HIT (similarity=%.2f) — reusing %s from %s",
            best_score,
            best_entry.get("dataset_ref", "?"),
            best_entry.get("provider", "?"),
        )
        # Increment use count
        best_entry["use_count"] = best_entry.get("use_count", 1) + 1
        self._save()
        return best_entry

    def record(
        self,
        spec: dict,
        provider: str,
        dataset_ref: str,
        local_path: str,
        row_count: int,
        columns: list[str],
        score: float,
        job_id: str = "",
    ) -> None:
        """
        Record a successful collection run into the experience database.
        Duplicates (same dataset_ref) are updated rather than appended.
        """
        # Check if we already have this dataset_ref; update if so
        for entry in self._entries:
            if entry.get("dataset_ref") == dataset_ref:
                entry["use_count"] = entry.get("use_count", 1) + 1
                entry["timestamp"] = _now()
                entry["local_path"] = local_path
                entry["row_count"] = row_count
                entry["columns"] = columns
                entry["score"] = round(score, 4)
                self._save()
                logger.info(
                    "ExperienceMemory: updated existing entry for %s (use_count=%d)",
                    dataset_ref, entry["use_count"],
                )
                return

        new_entry: dict[str, Any] = {
            "timestamp":    _now(),
            "job_id":       job_id,
            "intent":       spec.get("intent", ""),
            "task_type":    spec.get("task_type", ""),
            "domain":       spec.get("domain", ""),
            "keywords":     spec.get("keywords", []),
            "input_params": spec.get("input_params", []),
            "target_param": spec.get("target_param", ""),
            "provider":     provider,
            "dataset_ref":  dataset_ref,
            "row_count":    row_count,
            "columns":      columns,
            "local_path":   local_path,
            "score":        round(score, 4),
            "use_count":    1,
        }
        self._entries.append(new_entry)
        # Keep only the best 200 entries (pruning oldest by score)
        if len(self._entries) > 200:
            self._entries.sort(key=lambda e: (e.get("score", 0), e.get("use_count", 0)), reverse=True)
            self._entries = self._entries[:200]
        self._save()
        logger.info(
            "ExperienceMemory: recorded new entry — %s (provider=%s rows=%d score=%.3f)",
            dataset_ref, provider, row_count, score,
        )

    def stats(self) -> dict:
        """Return summary statistics for logging/debugging."""
        return {
            "total_entries":    len(self._entries),
            "total_uses":       sum(e.get("use_count", 0) for e in self._entries),
            "domains_covered":  list({e.get("domain", "") for e in self._entries}),
            "db_path":          str(self._db_path),
        }

    # ── Internals ──────────────────────────────────────────────────────────────

    def _load(self) -> list[dict]:
        if not self._db_path.exists():
            return []
        try:
            with open(self._db_path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception as exc:
            logger.warning("ExperienceMemory: could not load db (%s) — starting fresh", exc)
        return []

    def _save(self) -> None:
        try:
            with open(self._db_path, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, indent=2, default=str)
        except Exception as exc:
            logger.warning("ExperienceMemory: could not save db: %s", exc)

    @staticmethod
    def _similarity(spec: dict, entry: dict) -> float:
        """
        Token-overlap similarity between spec and a memory entry.
        Returns float in [0, 1].

        Scoring:
          +0.35 if task_type matches
          +0.25 if domain tokens overlap ≥ 50%
          +0.20 for keyword overlap ratio
          +0.10 for input_params overlap ratio
          +0.10 if target_param matches
        """
        score = 0.0

        # Task type (hard signal)
        if spec.get("task_type") == entry.get("task_type"):
            score += 0.35

        # Domain token overlap
        spec_domain_tokens = set(_tokenize(spec.get("domain", "")))
        entry_domain_tokens = set(_tokenize(entry.get("domain", "")))
        if spec_domain_tokens and entry_domain_tokens:
            overlap = len(spec_domain_tokens & entry_domain_tokens)
            denom = min(len(spec_domain_tokens), len(entry_domain_tokens))
            score += 0.25 * (overlap / denom)

        # Keyword overlap
        spec_kw = set(spec.get("keywords", []))
        entry_kw = set(entry.get("keywords", []))
        if spec_kw and entry_kw:
            score += 0.20 * (len(spec_kw & entry_kw) / max(len(spec_kw), len(entry_kw)))

        # Input params overlap
        spec_ip = set(_tokenize(" ".join(spec.get("input_params", []))))
        entry_ip = set(_tokenize(" ".join(entry.get("input_params", []))))
        if spec_ip and entry_ip:
            score += 0.10 * (len(spec_ip & entry_ip) / max(len(spec_ip), len(entry_ip)))

        # Target param
        if spec.get("target_param") and spec.get("target_param") == entry.get("target_param"):
            score += 0.10

        return min(1.0, score)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Simple whitespace+punctuation tokenizer."""
    return [t for t in re.sub(r"[^\w]", " ", text.lower()).split() if len(t) >= 2]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
