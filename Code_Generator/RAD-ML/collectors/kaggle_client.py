"""
collectors/kaggle_client.py - Kaggle Dataset Fetcher
====================================================
Searches Kaggle for the most relevant dataset matching the user's ML task,
downloads it, and returns structured metadata.
"""

from __future__ import annotations

import importlib.util
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)


# Check availability without importing kaggle at module import time.
KAGGLE_AVAILABLE = importlib.util.find_spec("kaggle") is not None
if not KAGGLE_AVAILABLE:
    log.warning("kaggle package not installed - KaggleClient will use mock data.")


DatasetMeta = Dict[str, object]


class KaggleClient:
    """
    Thin wrapper around the Kaggle API for dataset discovery + download.

    Args:
        cfg: Full config dict (reads [kaggle] section).
    """

    def __init__(self, cfg: dict):
        kaggle_cfg = cfg.get("kaggle", {})
        self.max_results = kaggle_cfg.get("max_results", 5)
        self.download_dir = Path("data/datasets")
        self.download_dir.mkdir(parents=True, exist_ok=True)

        # Set Kaggle env vars so the API picks them up.
        if kaggle_cfg.get("username") and "YOUR" not in kaggle_cfg["username"]:
            os.environ["KAGGLE_USERNAME"] = kaggle_cfg["username"]
            os.environ["KAGGLE_KEY"] = kaggle_cfg["key"]
            log.info("Kaggle credentials loaded from config.")
        else:
            log.warning("Kaggle credentials not set - using env variables if available.")

        self._api: Optional[object] = None

    def fetch(self, query: str) -> DatasetMeta:
        """
        Search Kaggle and download the best-matching dataset.
        """
        if not KAGGLE_AVAILABLE:
            return self._mock_meta(query)

        try:
            self._authenticate()
        except BaseException as exc:  # noqa: BLE001
            log.warning("Kaggle unavailable (%s). Using mock dataset.", exc)
            return self._mock_meta(query)

        datasets = self._search(query)
        if not datasets:
            log.warning("No Kaggle datasets found for query: %r", query)
            return self._mock_meta(query)

        best = self._pick_best(datasets)
        log.info("Selected dataset: %s (ref=%s)", best.title, best.ref)

        local_path = self._download(best.ref)
        csv_file = self._find_csv(local_path)

        return {
            "path": str(csv_file),
            "title": best.title,
            "ref": best.ref,
            "size_mb": round(best.totalBytes / 1_048_576, 2) if best.totalBytes else 0,
        }

    def fetch_by_ref(self, ref: str) -> DatasetMeta:
        """
        Download a specific Kaggle dataset by ref and return local CSV metadata.
        """
        if not ref or "/" not in ref:
            raise ValueError(f"Invalid Kaggle ref: {ref!r}")

        if not KAGGLE_AVAILABLE:
            return self._mock_meta(ref)

        try:
            self._authenticate()
        except BaseException as exc:  # noqa: BLE001
            log.warning("Kaggle unavailable (%s). Using mock dataset.", exc)
            return self._mock_meta(ref)

        local_path = self._download(ref)
        csv_file = self._find_csv(local_path)
        return {
            "path": str(csv_file),
            "title": ref.split("/", 1)[1].replace("-", " ").title(),
            "ref": ref,
            "size_mb": round(csv_file.stat().st_size / 1_048_576, 2),
        }

    def _authenticate(self) -> None:
        if self._api is not None:
            return
        try:
            from kaggle.api.kaggle_api_extended import KaggleApiExtended  # type: ignore
        except BaseException as exc:  # noqa: BLE001
            raise RuntimeError(f"Kaggle import failed: {exc}") from exc

        try:
            api = KaggleApiExtended()
            api.authenticate()
            self._api = api
            log.info("Kaggle API authenticated.")
        except BaseException as exc:  # noqa: BLE001
            raise RuntimeError(f"Kaggle auth failed: {exc}") from exc

    def _search(self, query: str) -> List:
        try:
            return self._api.dataset_list(search=query, page_size=self.max_results)
        except Exception as exc:
            log.error("Kaggle search failed: %s", exc)
            return []

    @staticmethod
    def _pick_best(datasets: List) -> object:
        """
        Heuristic: prefer datasets with highest vote count.
        """

        def score(ds):
            return getattr(ds, "voteCount", 0) or 0

        return sorted(datasets, key=score, reverse=True)[0]

    def _download(self, ref: str) -> Path:
        owner, name = ref.split("/")
        dest = self.download_dir / name
        dest.mkdir(parents=True, exist_ok=True)
        log.info("Downloading Kaggle dataset %s -> %s", ref, dest)
        self._api.dataset_download_files(ref, path=str(dest), unzip=True)
        return dest

    @staticmethod
    def _find_csv(directory: Path) -> Path:
        csvs = list(directory.glob("**/*.csv"))
        if not csvs:
            raise FileNotFoundError(f"No CSV found in {directory}")
        # Prefer the largest CSV (usually the main data file).
        return sorted(csvs, key=lambda p: p.stat().st_size, reverse=True)[0]

    @staticmethod
    def _mock_meta(query: str) -> DatasetMeta:
        mock_csv = Path("data/datasets/mock_dataset.csv")
        mock_csv.parent.mkdir(parents=True, exist_ok=True)
        if not mock_csv.exists():
            import csv

            with open(mock_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["feature_1", "feature_2", "feature_3", "target"])
                for i in range(100):
                    writer.writerow([i, i * 2, i * 0.5, i % 2])
        log.info("Using mock dataset at %s", mock_csv)
        return {
            "path": str(mock_csv),
            "title": f"Mock dataset for '{query}'",
            "ref": "mock/dataset",
            "size_mb": 0.01,
        }
