"""
collectors/ddg_scraper.py
=========================
DuckDuckGo search + recursive page scraping for chatbot RAG.

Key behavior:
1. Search using DDG for each keyword.
2. Scrape full page text for each result URL.
3. Clean, deduplicate, and relevance-filter scraped content.
4. Persist a corpus file for downstream vector indexing.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlsplit, urlunsplit

log = logging.getLogger(__name__)

try:
    from ddgs import DDGS  # type: ignore
    DDG_AVAILABLE = True
except ImportError:
    try:
        from duckduckgo_search import DDGS  # type: ignore
        DDG_AVAILABLE = True
    except ImportError:
        DDG_AVAILABLE = False
        log.warning("ddgs / duckduckgo_search is not installed; DDGScraper will use mock data.")

try:
    import requests
    from bs4 import BeautifulSoup  # type: ignore

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    log.warning("requests / beautifulsoup4 not installed; page scraping is disabled.")


Document = Dict[str, str]  # {title, url, content}


class DDGScraper:
    """Search DDG and scrape result pages into RAG-ready documents."""

    def __init__(self, cfg: dict):
        ddg_cfg = cfg.get("ddg", {})
        self.max_results = int(ddg_cfg.get("max_results", 10))
        self.timeout = int(ddg_cfg.get("timeout_secs", 8))
        self.min_length = int(ddg_cfg.get("min_doc_length", 100))
        self.max_chars = int(ddg_cfg.get("max_doc_chars", 8000))
        self.max_snippet_chars = int(ddg_cfg.get("max_snippet_chars", 1200))
        self.user_agent = str(
            ddg_cfg.get(
                "user_agent",
                "Mozilla/5.0 (compatible; RAD-ML-RAG/1.0)",
            )
        )
        self.persist_dir = Path(cfg.get("vector_store", {}).get("persist_dir", "data/vector_store"))
        self.persist_dir.mkdir(parents=True, exist_ok=True)

    def scrape(self, keywords: List[str], max_pages: int = 10) -> List[Document]:
        """
        Search DDG with the provided keywords, then scrape result URLs.
        """
        if not keywords:
            keywords = ["general information"]

        search_results: List[dict] = []
        for keyword in keywords:
            query = self._build_query(keyword)
            log.info("DDG search -> %r", query)
            results = self._search(query)
            for item in results:
                row = dict(item)
                row["_keyword"] = keyword
                search_results.append(row)

        return self.scrape_results(
            search_results=search_results,
            keywords=keywords,
            max_pages=max_pages,
        )

    def scrape_results(
        self,
        search_results: List[dict],
        keywords: Optional[List[str]] = None,
        max_pages: int = 10,
    ) -> List[Document]:
        """
        Convert existing DDG search results into scraped documents.
        """
        keywords = [str(k).strip().lower() for k in (keywords or []) if str(k).strip()]

        documents: List[Document] = []
        seen_urls: set[str] = set()
        seen_hashes: set[str] = set()

        for result in search_results:
            if len(documents) >= max_pages:
                break

            raw_url = str(result.get("href") or result.get("url") or "").strip()
            if not raw_url:
                continue
            norm_url = self._normalize_url(raw_url)
            if not norm_url or norm_url in seen_urls:
                continue
            seen_urls.add(norm_url)

            title = str(result.get("title") or "").strip()
            snippet = str(result.get("body") or result.get("snippet") or result.get("text") or "").strip()

            content = self._fetch_page(raw_url)
            if not content:
                content = self._fallback_content(title, snippet)

            content = self._clean(content)
            if self.max_chars > 0 and len(content) > self.max_chars:
                content = content[: self.max_chars]

            if len(content) < self.min_length:
                continue
            if keywords and self._keyword_overlap(f"{title} {content}", keywords) == 0:
                continue

            digest = hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()
            if digest in seen_hashes:
                continue
            seen_hashes.add(digest)

            documents.append(
                {
                    "title": title or norm_url,
                    "url": norm_url,
                    "content": content,
                }
            )

            time.sleep(0.3)

        log.info("DDGScraper finished -> %d documents collected.", len(documents))
        self._persist(documents)
        return documents

    @staticmethod
    def _build_query(keyword: str) -> str:
        return (
            f"{keyword} "
            "site:wikipedia.org OR site:medium.com OR site:towardsdatascience.com "
            "OR site:geeksforgeeks.org OR site:docs.python.org"
        )

    def _search(self, query: str) -> List[dict]:
        if not DDG_AVAILABLE:
            return self._mock_results(query)

        try:
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=self.max_results))
        except Exception as exc:
            log.error("DDG search failed: %s", exc)
            return []

    def _fetch_page(self, url: str) -> Optional[str]:
        if not REQUESTS_AVAILABLE:
            return None

        try:
            response = requests.get(
                url,
                timeout=self.timeout,
                headers={"User-Agent": self.user_agent},
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup(
                ["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]
            ):
                tag.decompose()

            text = self._extract_readable_text(soup)
            return self._clean(text)
        except Exception as exc:
            log.debug("Failed to fetch %s: %s", url, exc)
            return None

    @staticmethod
    def _extract_readable_text(soup) -> str:
        preferred = soup.find("article") or soup.find("main")
        if preferred:
            nodes = preferred.find_all(["h1", "h2", "h3", "p", "li"])
        else:
            nodes = soup.find_all(["h1", "h2", "h3", "p", "li"])

        chunks: List[str] = []
        for node in nodes:
            text = node.get_text(" ", strip=True)
            if len(text) >= 30:
                chunks.append(text)

        if not chunks:
            return soup.get_text(separator=" ", strip=True)
        return " ".join(chunks)

    def _fallback_content(self, title: str, snippet: str) -> str:
        text = self._clean(f"{title}. {snippet}")
        if self.max_snippet_chars > 0 and len(text) > self.max_snippet_chars:
            text = text[: self.max_snippet_chars]
        return text

    @staticmethod
    def _clean(text: str) -> str:
        text = re.sub(r"\s+", " ", str(text or ""))
        return text.strip()

    @staticmethod
    def _normalize_url(url: str) -> str:
        url = str(url or "").strip()
        if not url:
            return ""
        try:
            parts = urlsplit(url)
            if parts.scheme not in {"http", "https"} or not parts.netloc:
                return ""
            normalized = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, "", ""))
            return normalized.rstrip("/")
        except Exception:
            return ""

    @staticmethod
    def _keyword_overlap(text: str, keywords: List[str]) -> int:
        text_l = str(text or "").lower()
        return sum(1 for kw in keywords if len(kw) >= 3 and kw in text_l)

    def _persist(self, documents: List[Document]) -> None:
        corpus_path = self.persist_dir / "corpus.txt"
        with open(corpus_path, "w", encoding="utf-8") as handle:
            for doc in documents:
                handle.write(f"=== {doc.get('title', '')} ===\n")
                handle.write(f"URL: {doc.get('url', '')}\n")
                handle.write(doc.get("content", ""))
                handle.write("\n\n")
        log.info("Corpus saved -> %s", corpus_path)

    @staticmethod
    def _mock_results(query: str) -> List[dict]:
        return [
            {
                "title": f"Mock article about {query}",
                "href": f"https://example.com/{query.replace(' ', '_')}",
                "body": f"Mock content about {query}.",
            }
        ]
