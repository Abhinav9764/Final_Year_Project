"""
collectors/ddg_search.py
========================
DuckDuckGo search wrapper for the RAD-ML data collection agent.

Performs text searches via the ``duckduckgo_search`` library and optionally
fetches the full body text of result URLs for downstream reward scoring.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result type alias
# ---------------------------------------------------------------------------

SearchResult = dict[str, str]   # {title, url, snippet}


# ---------------------------------------------------------------------------
# DDG Search Client
# ---------------------------------------------------------------------------

class DDGSearchClient:
    """
    Wraps the ``duckduckgo_search`` library for query-based web search.

    Parameters
    ----------
    config : dict
        The ``collection`` section of config.yaml.
    """

    def __init__(self, config: dict) -> None:
        self._max_results: int = config.get("max_ddg_results", 10)
        self._timeout: int = config.get("ddg_timeout", 20)

        # Validate early
        if self._max_results < 1:
            raise ValueError(
                f"max_ddg_results must be >= 1, got {self._max_results}"
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_ddgs():
        """Import DDGS lazily so the rest of the codebase loads without it."""
        try:
            from duckduckgo_search import DDGS  # noqa: PLC0415
            return DDGS
        except ImportError as exc:
            raise ImportError(
                "duckduckgo-search is not installed. "
                "Run: pip install duckduckgo-search"
            ) from exc

    @staticmethod
    def _fetch_page_text(url: str, timeout: int = 10) -> str:
        """
        Fetch and extract plain text from a URL.

        Returns an empty string on any network or parsing error,
        so failures are silent and non-blocking.
        """
        try:
            import requests  # noqa: PLC0415
            from bs4 import BeautifulSoup  # noqa: PLC0415

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (compatible; RAD-ML-Agent/1.0)"
                )
            }
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")
            # Remove script and style noise
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()

            text = soup.get_text(separator=" ", strip=True)
            return text

        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not fetch '%s': %s", url, exc)
            return ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        fetch_text: bool = False,
        retry_on_rate_limit: bool = True,
    ) -> list[SearchResult]:
        """
        Run a DuckDuckGo text search for *query*.

        Parameters
        ----------
        query : str
            Search string (ideally the primary keywords joined by spaces).
        fetch_text : bool
            If True, also fetches the full page text for each result URL.
            This enriches the reward computation but adds latency.
        retry_on_rate_limit : bool
            Automatically wait and retry once on HTTP 202 / rate-limit errors.

        Returns
        -------
        list[SearchResult]
            Each item is ``{title, url, snippet, text}`` (``text`` is empty
            unless ``fetch_text=True``).

        Raises
        ------
        ValueError
            If *query* is empty.
        RuntimeError
            If the DDG API returns an unrecoverable error.
        """
        if not query or not query.strip():
            raise ValueError("Search query must be a non-empty string.")

        query = query.strip()
        DDGS = self._get_ddgs()
        results: list[SearchResult] = []

        logger.info("DDG search: '%s' (max %d results)", query, self._max_results)

        try:
            with DDGS(timeout=self._timeout) as ddgs:
                raw: list[dict[str, Any]] = list(
                    ddgs.text(query, max_results=self._max_results)
                )
        except Exception as exc:
            err_msg = str(exc).lower()
            if retry_on_rate_limit and ("202" in err_msg or "rate" in err_msg):
                logger.warning(
                    "DDG rate-limit detected. Waiting 5 s then retrying…"
                )
                time.sleep(5)
                try:
                    with DDGS(timeout=self._timeout) as ddgs:
                        raw = list(
                            ddgs.text(query, max_results=self._max_results)
                        )
                except Exception as retry_exc:
                    raise RuntimeError(
                        f"DDG search failed after retry: {retry_exc}"
                    ) from retry_exc
            else:
                raise RuntimeError(f"DDG search error: {exc}") from exc

        for item in raw:
            result: SearchResult = {
                "title":   item.get("title", ""),
                "url":     item.get("href", ""),
                "snippet": item.get("body", ""),
                "text":    "",
            }
            if fetch_text and result["url"]:
                logger.debug("Fetching full text for: %s", result["url"])
                result["text"] = self._fetch_page_text(result["url"])

            results.append(result)

        logger.info(
            "DDG returned %d results for '%s'.", len(results), query
        )
        return results
