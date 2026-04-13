"""
collectors/uci_collector.py
============================
Searches the UCI Machine Learning Repository via its public REST API.
No API key needed — completely free.
Returns metadata and downloads CSVs for qualifying datasets.
"""
from __future__ import annotations
import logging
import re
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

UCI_SEARCH_URL = "https://archive.ics.uci.edu/api/datasets"
UCI_DOWNLOAD_BASE = "https://archive.ics.uci.edu/static/public"


class UCICollector:
    def __init__(self, config: dict):
        cfg = config.get("uci", {})
        col = config.get("collection", {})
        self._enabled  = cfg.get("enabled", True)
        self._max      = int(col.get("max_uci_results", 10))
        self._raw_dir  = Path(col.get("raw_data_dir", "data/raw"))
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        self._session  = requests.Session()
        self._session.headers["User-Agent"] = "RAD-ML-Research-Bot/1.0"

    # ── public ────────────────────────────────────────────────────────────────
    def search(self, query: str) -> list[dict]:
        """Return metadata dicts for matching UCI datasets."""
        if not self._enabled:
            return []
        try:
            resp = self._session.get(
                UCI_SEARCH_URL,
                params={"search": query, "take": self._max, "skip": 0},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("UCI search failed for '%s': %s", query, exc)
            return []

        results = []
        for item in data.get("result", {}).get("results", []):
            results.append({
                "source":     "uci",
                "ref":        str(item.get("id", "")),
                "title":      item.get("name", ""),
                "url":        f"https://archive.ics.uci.edu/dataset/{item.get('id','')}",
                "size_mb":    0.0,
                "vote_count": int(item.get("numHits", 0)),
                "num_instances": int(item.get("numInstances", 0) or 0),
                "num_features":  int(item.get("numFeatures", 0)  or 0),
                "local_path": None,
            })
        return results

    def download(self, dataset_id: str) -> list[Path]:
        """
        Download a UCI dataset by its numeric ID.
        Tries the standard CSV download URL pattern.
        """
        dest = self._raw_dir / f"uci_{dataset_id}"
        dest.mkdir(parents=True, exist_ok=True)

        # UCI provides a zip of the dataset at /static/public/{id}/{id}.zip
        zip_url = f"{UCI_DOWNLOAD_BASE}/{dataset_id}/{dataset_id}.zip"
        try:
            resp = self._session.get(zip_url, timeout=60, stream=True)
            resp.raise_for_status()
            zip_path = dest / f"{dataset_id}.zip"
            with open(zip_path, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
            import zipfile
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(dest)
            zip_path.unlink()
        except Exception as exc:
            logger.warning("UCI download failed for id=%s: %s", dataset_id, exc)
            # Try direct CSV endpoint
            return self._try_direct_csv(dataset_id, dest)

        csv_paths = list(dest.rglob("*.csv"))
        if not csv_paths:
            csv_paths = self._try_direct_csv(dataset_id, dest)
        logger.info("UCI download: %d CSV(s) from id=%s", len(csv_paths), dataset_id)
        return csv_paths

    def _try_direct_csv(self, dataset_id: str, dest: Path) -> list[Path]:
        """Fallback: fetch the dataset detail page and look for CSV links."""
        try:
            resp = self._session.get(
                f"https://archive.ics.uci.edu/api/datasets/{dataset_id}",
                timeout=15,
            )
            resp.raise_for_status()
            detail = resp.json().get("result", {})
            csv_url = detail.get("externalLink") or detail.get("downloadUrl") or ""
            if csv_url and csv_url.endswith(".csv"):
                r = self._session.get(csv_url, timeout=60)
                r.raise_for_status()
                p = dest / "data.csv"
                p.write_bytes(r.content)
                return [p]
        except Exception as exc:
            logger.debug("UCI direct CSV fallback failed: %s", exc)
        return []
