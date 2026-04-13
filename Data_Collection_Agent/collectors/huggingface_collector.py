"""
collectors/huggingface_collector.py  (v2 — permanent fix)
==========================================================
HuggingFace Datasets collector — works as both Tier 1 and Tier 4 source.

ROOT CAUSE FIXES (v2):
  - `list_datasets(task="tabular-classification")` was INVALID since
    huggingface_hub v0.20: the `task` parameter was removed.
    All searches silently returned 0 results or raised an exception
    that was caught and discarded.
  - Fixed to use `filter="task_categories:tabular-classification"` which
    is the correct filter syntax for modern huggingface_hub.
  - Added Strategy 3: search by task-type tags (tabular-regression,
    tabular-classification, etc.) to maximise recall.
  - All exceptions are now logged at WARNING level (not silently ignored).

Features:
- Searches HuggingFace Hub for tabular datasets using 3 strategies
- Downloads datasets in parquet/CSV format via `datasets` library
- Graceful fallback with no API key required
- Rate-limit friendly: cached results locally
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Mapping from task_type keywords to HuggingFace task category tags
_TASK_TAG_MAP = {
    "classification": "tabular-classification",
    "regression":     "tabular-regression",
    "clustering":     "tabular-classification",   # best proxy for unsupervised
    "chatbot":        "question-answering",
}


class HuggingFaceCollector:
    def __init__(self, config: dict):
        col    = config.get("collection", {})
        hf_cfg = config.get("huggingface", {})

        self._max      = int(col.get("max_hf_results", 8))
        self._min_rows = int(col.get("min_row_threshold", 500))
        self._raw_dir  = Path(col.get("raw_data_dir", "data/raw"))
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        self._enabled  = hf_cfg.get("enabled", True)
        self.last_error = ""

    # ── public ────────────────────────────────────────────────────────────────

    def search(self, query: str, spec: dict | None = None) -> list[dict]:
        """
        Search HuggingFace Hub for datasets. Returns empty list on failure.

        Strategy 1: filter by task-category tag + keyword search (correct API)
        Strategy 2: general keyword search without task filter
        Strategy 3: tag-only search using task type
        """
        self.last_error = ""

        if not self._enabled:
            return []

        try:
            from huggingface_hub import list_datasets
        except ImportError:
            self.last_error = (
                "huggingface_hub not installed. "
                "Install with: pip install huggingface_hub>=0.20.0"
            )
            logger.warning("%s", self.last_error)
            return []

        keywords = [k.strip().lower() for k in query.split() if len(k.strip()) >= 3]
        results:  list[dict] = []
        seen_ids: set[str]   = set()

        # ── Expanded keyword aliases ──────────────────────────────────────────
        expanded_kw = list(keywords)
        keyword_aliases = {
            "movie":          ["movies", "film", "cinema", "recommendation"],
            "movies":         ["movie", "film"],
            "recommendation": ["recommend", "recommendations", "recommender"],
            "house":          ["housing", "real-estate"],
            "housing":        ["house", "real-estate"],
            "price":          ["prices", "pricing"],
            "predict":        ["prediction"],
            "classify":       ["classification"],
        }
        for kw in keywords:
            if kw in keyword_aliases:
                expanded_kw.extend(keyword_aliases[kw])
        expanded_kw = list(dict.fromkeys(expanded_kw))  # dedup, preserve order

        # ── Determine task category tag ───────────────────────────────────────
        task_type = (spec or {}).get("task_type", "classification")
        task_tag  = _TASK_TAG_MAP.get(task_type, "tabular-classification")

        # ── Strategy 1: task-category filter + keyword search (v0.20+ API) ───
        for kw in expanded_kw[:3]:
            try:
                # FIXED: use filter= instead of deprecated task=
                datasets_iter = list_datasets(
                    search=kw,
                    filter=f"task_categories:{task_tag}",
                    limit=self._max * 2,
                    full=False,
                )
                for dataset_info in datasets_iter:
                    dataset_id = dataset_info.id
                    if dataset_id in seen_ids:
                        continue
                    seen_ids.add(dataset_id)
                    results.append(self._make_meta(dataset_id))
                    if len(results) >= self._max:
                        break

            except Exception as exc:
                logger.warning("HuggingFace Strategy 1 search '%s': %s", kw, exc)

            if len(results) >= self._max:
                break

        # ── Strategy 2: general keyword search (no task filter) ──────────────
        if len(results) < self._max:
            try:
                datasets_iter = list_datasets(
                    search=" ".join(expanded_kw[:2]),
                    limit=self._max * 3,
                    full=False,
                )
                for dataset_info in datasets_iter:
                    dataset_id = dataset_info.id
                    if dataset_id in seen_ids:
                        continue
                    seen_ids.add(dataset_id)
                    results.append(self._make_meta(dataset_id))
                    if len(results) >= self._max:
                        break

            except Exception as exc:
                logger.warning("HuggingFace Strategy 2 general search: %s", exc)

        # ── Strategy 3: task-tag-only search (broadest, no keyword) ──────────
        if not results:
            try:
                datasets_iter = list_datasets(
                    filter=f"task_categories:{task_tag}",
                    limit=self._max * 2,
                    full=False,
                )
                for dataset_info in datasets_iter:
                    dataset_id = dataset_info.id
                    if dataset_id in seen_ids:
                        continue
                    seen_ids.add(dataset_id)
                    results.append(self._make_meta(dataset_id))
                    if len(results) >= self._max:
                        break

            except Exception as exc:
                logger.warning("HuggingFace Strategy 3 tag search '%s': %s", task_tag, exc)
                self.last_error = f"HuggingFace search failed: {exc}"
                return []

        logger.info("HuggingFace search '%s' → %d results", query, len(results))
        return results[: self._max]

    def download(self, dataset_id: str) -> list[Path]:
        """Download HuggingFace dataset and convert to CSV."""
        self.last_error = ""

        try:
            from datasets import load_dataset
            import pandas as pd
        except ImportError:
            self.last_error = (
                "datasets library not installed. "
                "Install with: pip install datasets>=2.14.0"
            )
            logger.error("%s", self.last_error)
            return []

        dest     = self._raw_dir / f"huggingface_{dataset_id.replace('/', '_')}"
        dest.mkdir(parents=True, exist_ok=True)
        csv_path = dest / "data.csv"

        # Check if already cached
        if csv_path.exists() and csv_path.stat().st_size > 1024:
            logger.info("HuggingFace %s: using cached CSV", dataset_id)
            return [csv_path]

        try:
            logger.info("HuggingFace: downloading dataset '%s'...", dataset_id)

            # Try train split first, fallback to no split spec
            dataset = None
            for split_arg in [{"split": "train"}, {}]:
                try:
                    dataset = load_dataset(dataset_id, streaming=False, **split_arg)
                    break
                except Exception:
                    pass

            if dataset is None:
                self.last_error = f"HuggingFace: could not load any split for '{dataset_id}'"
                logger.warning("%s", self.last_error)
                return []

            # If a DatasetDict was returned, pick the largest split
            if hasattr(dataset, "keys"):
                best_split = max(dataset.keys(), key=lambda k: len(dataset[k]))
                dataset = dataset[best_split]

            # Convert to DataFrame
            if hasattr(dataset, "to_pandas"):
                df = dataset.to_pandas()
            elif isinstance(dataset, pd.DataFrame):
                df = dataset
            else:
                # Last resort — try to force it into a DataFrame
                df = pd.DataFrame(dataset)

            # Enforce minimum rows requirement
            if len(df) < self._min_rows:
                self.last_error = (
                    f"HuggingFace dataset '{dataset_id}' has only {len(df)} rows "
                    f"(minimum required: {self._min_rows})"
                )
                logger.warning("%s", self.last_error)
                return []

            df.to_csv(csv_path, index=False)
            logger.info("HuggingFace: saved %d rows to %s", len(df), csv_path)
            return [csv_path]

        except Exception as exc:
            self.last_error = f"HuggingFace download failed for '{dataset_id}': {exc}"
            logger.error("%s", self.last_error)
            return []

    def search_by_id(self, dataset_id: str) -> list[dict]:
        """
        Resolve metadata for a known HuggingFace dataset ID.
        Always returns a stub even if the API cannot be reached.
        """
        self.last_error = ""

        stub = [self._make_meta(dataset_id)]

        try:
            from huggingface_hub import dataset_info
            dinfo = dataset_info(dataset_id)
            return [{
                "source":     "huggingface",
                "ref":        dataset_id,
                "title":      getattr(dinfo, "id", dataset_id).replace("_", " ").title(),
                "url":        f"https://huggingface.co/datasets/{dataset_id}",
                "size_mb":    0,
                "vote_count": getattr(dinfo, "likes", 0) or 0,
                "local_path": None,
            }]
        except Exception as exc:
            logger.debug("HuggingFace search_by_id failed for '%s': %s", dataset_id, exc)
            return stub

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _make_meta(dataset_id: str) -> dict:
        return {
            "source":     "huggingface",
            "ref":        dataset_id,
            "title":      dataset_id.replace("_", " ").replace("/", " / ").title(),
            "url":        f"https://huggingface.co/datasets/{dataset_id}",
            "size_mb":    0,
            "vote_count": 0,
            "local_path": None,
        }
