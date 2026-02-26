"""
collectors/kaggle_client.py
============================
Kaggle API wrapper for the RAD-ML data collection agent.

Authenticates from config.yaml (sets OS env-vars before calling the
Kaggle client so no ~/.kaggle/kaggle.json is required).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Result type alias
DatasetInfo = dict[str, Any]   # {ref, title, size, tags, url}


class KaggleClient:
    """
    Wraps the ``kaggle`` Python SDK for dataset search and download.

    Credentials are pulled from ``config["kaggle"]`` (username + key)
    and injected as environment variables, so no ``~/.kaggle/kaggle.json``
    is needed.

    Parameters
    ----------
    config : dict
        Full config dict (uses ``config["kaggle"]`` and
        ``config["collection"]``).
    """

    def __init__(self, config: dict) -> None:
        kaggle_cfg: dict = config.get("kaggle", {})
        self._username: str = kaggle_cfg.get("username", "")
        self._key: str = kaggle_cfg.get("key", "")
        self._max_datasets: int = config.get("collection", {}).get(
            "max_kaggle_datasets", 5
        )
        self._download: bool = config.get("collection", {}).get(
            "download_kaggle", True
        )
        self._raw_dir: Path = Path(
            config.get("collection", {}).get("raw_data_dir", "data/raw")
        )
        self._api = None  # Lazy initialised

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_auth(self) -> None:
        """
        Authenticate the Kaggle API using credentials from config.

        Raises
        ------
        ValueError
            If username or key are placeholder / missing values.
        ImportError
            If the ``kaggle`` package is not installed.
        RuntimeError
            If the Kaggle API raises an authentication error.
        """
        if self._api is not None:
            return  # Already authenticated

        if not self._username or self._username == "YOUR_KAGGLE_USERNAME":
            raise ValueError(
                "Kaggle username not configured. "
                "Set 'kaggle.username' in config.yaml."
            )
        if not self._key or self._key == "YOUR_KAGGLE_API_KEY":
            raise ValueError(
                "Kaggle API key not configured. "
                "Set 'kaggle.key' in config.yaml."
            )

        # Inject credentials as environment variables
        os.environ["KAGGLE_USERNAME"] = self._username
        os.environ["KAGGLE_KEY"] = self._key

        try:
            from kaggle.api.kaggle_api_extended import (  # noqa: PLC0415
                KaggleApiExtended,
            )

            api = KaggleApiExtended()
            api.authenticate()
            self._api = api
            logger.info("Kaggle API authenticated as '%s'.", self._username)

        except ImportError as exc:
            raise ImportError(
                "kaggle package is not installed. Run: pip install kaggle"
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"Kaggle authentication failed: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search_datasets(self, keywords: list[str]) -> list[DatasetInfo]:
        """
        Search Kaggle for datasets matching *keywords*.

        Parameters
        ----------
        keywords : list[str]
            Primary keywords extracted from the user prompt.

        Returns
        -------
        list[DatasetInfo]
            Up to ``max_kaggle_datasets`` entries, each containing
            ``ref``, ``title``, ``size``, ``tags``, and ``url``.

        Raises
        ------
        ValueError
            If *keywords* is empty.
        RuntimeError
            If the Kaggle API call fails.
        """
        if not keywords:
            raise ValueError("At least one keyword must be provided.")

        self._ensure_auth()

        query = " ".join(keywords[:3])   # Use top-3 keywords for API search
        logger.info(
            "Kaggle dataset search: '%s' (max %d)", query, self._max_datasets
        )

        try:
            datasets = self._api.dataset_list(
                search=query,
                file_type="all",
                license_name="all",
                page_size=self._max_datasets,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Kaggle dataset_list failed for query '{query}': {exc}"
            ) from exc

        results: list[DatasetInfo] = []
        for ds in datasets:
            try:
                ref = ds.ref if hasattr(ds, "ref") else str(ds)
                info: DatasetInfo = {
                    "ref":   ref,
                    "title": getattr(ds, "title", ref),
                    "size":  getattr(ds, "totalBytes", 0),
                    "tags":  [t.name for t in getattr(ds, "tags", [])],
                    "url":   f"https://www.kaggle.com/datasets/{ref}",
                }
                results.append(info)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not parse dataset entry: %s", exc)

        logger.info("Kaggle returned %d datasets.", len(results))
        return results

    def download_dataset(self, ref: str) -> Path:
        """
        Download a Kaggle dataset by its *ref* (``owner/dataset-name``).

        Parameters
        ----------
        ref : str
            Dataset reference in ``owner/dataset-name`` format.

        Returns
        -------
        Path
            Directory where the dataset was downloaded.

        Raises
        ------
        ValueError
            If *ref* is not in the expected format.
        RuntimeError
            If the download fails.
        """
        if not ref or "/" not in ref:
            raise ValueError(
                f"Dataset ref must be 'owner/dataset-name', got: '{ref}'"
            )

        if not self._download:
            logger.info(
                "Kaggle download disabled (download_kaggle=false). Skipping '%s'.",
                ref,
            )
            return self._raw_dir

        self._ensure_auth()

        dest = self._raw_dir / ref.replace("/", "_")
        dest.mkdir(parents=True, exist_ok=True)

        logger.info("Downloading Kaggle dataset '%s' → %s", ref, dest)
        try:
            self._api.dataset_download_files(
                dataset=ref,
                path=str(dest),
                unzip=True,
                quiet=False,
            )
            logger.info("Download complete: '%s'", dest)
            return dest

        except Exception as exc:
            raise RuntimeError(
                f"Failed to download Kaggle dataset '{ref}': {exc}"
            ) from exc
