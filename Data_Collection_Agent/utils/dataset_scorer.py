"""
utils/dataset_scorer.py
========================
Scores dataset candidates using a transparent weighted formula.
NO reinforcement learning — pure deterministic relevance scoring.

Score = w_kw * keyword_score
      + w_row * row_score
      + w_col * column_score
      + w_rec * recency_score

All sub-scores are normalised to [0, 1].
"""
from __future__ import annotations
import logging
import re
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


class DatasetScorer:
    def __init__(self, config: dict):
        sc = config.get("scoring", {})
        self._w_kw  = float(sc.get("keyword_match_weight", 0.40))
        self._w_row = float(sc.get("row_count_weight",     0.30))
        self._w_col = float(sc.get("column_match_weight",  0.20))
        self._w_rec = float(sc.get("recency_weight",       0.10))
        self._min_rows = int(config.get("collection", {}).get("min_row_threshold", 500))

    # ── public ────────────────────────────────────────────────────────────────
    def score_metadata(self, meta: dict, spec: dict) -> float:
        """
        Score a dataset candidate from its metadata alone (before download).
        Used to rank candidates and decide which to download first.
        """
        kw_score  = self._keyword_score_meta(meta, spec)
        row_score = self._row_score_from_meta(meta)
        rec_score = self._recency_score(meta)
        # column score not available pre-download
        total = (self._w_kw * kw_score
                 + self._w_row * row_score
                 + self._w_rec * rec_score)
        meta["pre_score"] = round(total, 4)
        return total

    def score_csv(self, csv_path: Path, meta: dict, spec: dict) -> float:
        """
        Full score after the CSV is downloaded.
        Penalises datasets that don't contain columns matching input_params/target.
        """
        try:
            df = pd.read_csv(csv_path, nrows=5)
            cols_lower = [c.lower() for c in df.columns]
            row_count  = self._count_rows(csv_path)
        except Exception as exc:
            logger.warning("Cannot read %s for scoring: %s", csv_path, exc)
            return 0.0

        kw_score  = self._keyword_score_meta(meta, spec)
        row_score = self._row_score(row_count)
        col_score = self._column_score(cols_lower, spec)
        rec_score = self._recency_score(meta)

        total = (self._w_kw  * kw_score
                 + self._w_row * row_score
                 + self._w_col * col_score
                 + self._w_rec * rec_score)

        # Penalise datasets with zero feature match — strong signal of irrelevance
        params = spec.get("input_params", []) + [spec.get("target_param", "")]
        params = [p for p in params if p]
        if params and col_score == 0.0:
            total *= 0.5
            logger.info("Zero feature match penalty applied for %s", csv_path.name)

        meta["final_score"] = round(total, 4)
        meta["row_count"]   = row_count
        logger.info("Scored %s → %.3f  (kw=%.2f row=%.2f col=%.2f rec=%.2f)",
                    csv_path.name, total, kw_score, row_score, col_score, rec_score)
        return total

    # ── sub-scores ────────────────────────────────────────────────────────────
    def _keyword_score_meta(self, meta: dict, spec: dict) -> float:
        """Fraction of keywords found in dataset title."""
        keywords  = spec.get("keywords", [])
        if not keywords:
            return 0.5
        title = (meta.get("title","") + " " + meta.get("ref","")).lower()
        hits  = sum(1 for kw in keywords if kw.lower() in title)
        return hits / len(keywords)

    def _row_score_from_meta(self, meta: dict) -> float:
        """Use num_instances from UCI or estimate from size_mb for Kaggle."""
        ni = meta.get("num_instances", 0) or 0
        if ni:
            return self._row_score(ni)
        mb = meta.get("size_mb", 0) or 0
        estimated_rows = mb * 3000  # rough: 1 MB ≈ 3000 rows for typical CSV
        return self._row_score(estimated_rows)

    def _row_score(self, n: int | float) -> float:
        if n >= self._min_rows:
            # Good: saturates quickly above threshold
            return min(1.0, 0.7 + 0.3 * (n - self._min_rows) / max(self._min_rows, 1))
        # Penalise below threshold
        return max(0.0, n / self._min_rows)

    def _column_score(self, cols: list[str], spec: dict) -> float:
        """How many of the user's specified input_params appear as columns."""
        params = spec.get("input_params", []) + [spec.get("target_param","")]
        params = [p for p in params if p]
        if not params:
            return 0.5
        hits = sum(1 for p in params
                   if any(p.lower() in c or c in p.lower() for c in cols))
        return hits / len(params)

    def _recency_score(self, meta: dict) -> float:
        """Proxy for recency: normalised vote/hit count."""
        votes = meta.get("vote_count", 0) or 0
        return min(1.0, votes / 500)  # 500+ votes → perfect score

    @staticmethod
    def _count_rows(csv_path: Path) -> int:
        try:
            with open(csv_path, "rb") as f:
                return sum(1 for _ in f) - 1  # subtract header
        except Exception:
            return 0
