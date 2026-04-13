"""
collectors/openml_collector.py  (v8)
=======================================
ROOT CAUSE FIX:
  - list_datasets() was called without limit → fetched ALL 10,000+ datasets,
    caused network timeouts and memory issues.
  - Now uses targeted search: list_datasets(tag=keyword) which is fast,
    AND a size-limited fetch (500 datasets max, filtered by name).
  - Falls back gracefully (returns []) on any error — never crashes pipeline.
"""
from __future__ import annotations
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class OpenMLCollector:
    def __init__(self, config: dict):
        col        = config.get("collection", {})
        openml_cfg = config.get("openml", {})
        self._max      = int(col.get("max_openml_results", 8))
        self._min_rows = int(col.get("min_row_threshold", 500))
        self._raw_dir  = Path(col.get("raw_data_dir", "data/raw"))
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        self._enabled  = openml_cfg.get("enabled", True)
        self._api_key = str(os.getenv("OPENML_API_KEY") or openml_cfg.get("api_key", "")).strip()
        self._configured = False

    def _load_openml(self):
        import openml

        if not self._configured and self._api_key and not self._api_key.startswith("YOUR_"):
            openml.config.apikey = self._api_key
        self._configured = True
        return openml

    # ── public ──────────────────────────────────────────────────────────────
    def search(self, query: str, spec: dict | None = None) -> list[dict]:
        if not self._enabled:
            return []
        try:
            openml = self._load_openml()
        except ImportError:
            logger.warning("openml not installed: pip install openml")
            return []

        keywords = [k.strip().lower() for k in query.split() if len(k.strip()) >= 3]
        # Expand keywords to include related terms for better coverage
        expanded_kw = list(keywords)
        keyword_aliases = {
            "movie": ["movies", "film", "cinema"],
            "movies": ["movie", "film"],
            "film": ["movie", "movies"],
            "rating": ["ratings", "score", "rank"],
            "ratings": ["rating", "votes"],
            "recommendation": ["recommend", "recommendations", "recommender"],
        }
        for kw in keywords:
            if kw in keyword_aliases:
                expanded_kw.extend(keyword_aliases[kw])
        expanded_kw = list(dict.fromkeys(expanded_kw))  # dedup
        
        results: list[dict] = []
        seen_ids: set[str]  = set()

        # Strategy 1: tag search for each keyword (fast — targeted API call)
        for kw in expanded_kw[:5]:
            try:
                tag_ds = openml.datasets.list_datasets(
                    tag=kw, output_format="dataframe"
                )
                if tag_ds is not None and len(tag_ds) > 0:
                    logger.debug("OpenML tag search '%s' found %d datasets", kw, len(tag_ds))
                    for did, row in tag_ds.iterrows():
                        ref = str(did)
                        if ref in seen_ids:
                            continue
                        n_inst = int(row.get("NumberOfInstances", 0) or 0)
                        if n_inst < 50:
                            continue
                        seen_ids.add(ref)
                        results.append(self._make_meta(did, row))
                        if len(results) >= self._max:
                            break
                if len(results) >= self._max:
                    break
            except Exception as exc:
                logger.debug("OpenML tag search '%s': %s", kw, exc)
            if len(results) >= self._max:
                break

        # Strategy 2: name-based search on a size-limited batch
        if len(results) < self._max:
            try:
                # Fetch only first 500 datasets (much faster than all 10k+)
                batch = openml.datasets.list_datasets(
                    output_format="dataframe",
                    offset=0, size=500
                )
                if batch is not None and len(batch) > 0:
                    logger.debug("OpenML batch search: fetched %d datasets for name matching", len(batch))
                    for kw in expanded_kw[:3]:
                        mask = batch["name"].str.lower().str.contains(kw, na=False)
                        matched = batch[mask]
                        logger.debug("OpenML name search '%s': %d matches", kw, len(matched))
                        for did, row in matched.iterrows():
                            ref = str(did)
                            if ref in seen_ids:
                                continue
                            n_inst = int(row.get("NumberOfInstances", 0) or 0)
                            if n_inst < 50:
                                continue
                            seen_ids.add(ref)
                            results.append(self._make_meta(did, row))
                        if len(results) >= self._max:
                            break
            except Exception as exc:
                logger.debug("OpenML batch search: %s", exc)

        # Sort by size descending (bigger = better for ML training)
        results.sort(key=lambda r: r.get("num_instances", 0), reverse=True)
        logger.info("OpenML search '%s' → %d results", query, len(results))
        return results[: self._max]

    def download(self, dataset_id: str) -> list[Path]:
        try:
            openml = self._load_openml()
        except ImportError:
            return []

        dest     = self._raw_dir / f"openml_{dataset_id}"
        dest.mkdir(parents=True, exist_ok=True)
        csv_path = dest / "data.csv"

        if csv_path.exists() and csv_path.stat().st_size > 1024:
            logger.info("OpenML %s: using cached CSV", dataset_id)
            return [csv_path]

        try:
            ds = openml.datasets.get_dataset(
                int(dataset_id),
                download_data=True,
                download_qualities=False,
                download_features_meta_data=False,
            )
            X, y, _, _ = ds.get_data(dataset_format="dataframe")
            import pandas as pd
            df = X.copy()
            if y is not None:
                df[ds.default_target_attribute or "target"] = y.values
            df.to_csv(csv_path, index=False)
            logger.info("OpenML %s: %d rows × %d cols", dataset_id, len(df), len(df.columns))
            return [csv_path]
        except Exception as exc:
            logger.error("OpenML download id=%s: %s", dataset_id, exc)
            return []

    @staticmethod
    def _make_meta(did, row) -> dict:
        n_inst = int(row.get("NumberOfInstances", 0) or 0)
        n_feat = int(row.get("NumberOfFeatures",  0) or 0)
        return {
            "source":        "openml",
            "ref":           str(did),
            "title":         str(row.get("name", f"openml_{did}")),
            "url":           f"https://www.openml.org/d/{did}",
            "size_mb":       round(n_inst * n_feat * 8 / 1_000_000, 2),
            "vote_count":    0,
            "num_instances": n_inst,
            "num_features":  n_feat,
            "missing_rate":  0.0,
            "local_path":    None,
        }
