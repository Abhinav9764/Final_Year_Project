import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import quote_plus

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true"
RAG_ENABLE_WEB = os.getenv("RAG_ENABLE_WEB", "false").lower() == "true"

class WebRAGEngine:
    def __init__(self):
        self.headers = {
            "User-Agent": "RAD-ML-Bot/1.0 (Educational)",
            "Accept": "text/html,application/json"
        }

    def _ollama_available(self):
        try:
            r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def _ollama_chat(self, model, messages, temperature=0.2, num_predict=512):
        payload = {
            "model": model,
            "messages": messages,
            "options": {"temperature": temperature, "num_predict": num_predict},
            "stream": False
        }
        r = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=20)
        r.raise_for_status()
        return r.json()["message"]["content"]

    def _clean_text(self, text):
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _wiki_search(self, query, max_results=2):
        try:
            url = "https://en.wikipedia.org/w/api.php"
            params = {"action":"query","format":"json","list":"search","srsearch":query,"srlimit":max_results}
            r = requests.get(url, params=params, headers=self.headers, timeout=8)
            if r.status_code != 200:
                return []
            data = r.json()
            results = []
            for item in data.get("query", {}).get("search", []):
                pageid = item.get("pageid")
                extract = self._wiki_extract(pageid)
                if extract:
                    results.append({"source":"Wikipedia","title":item.get("title"),"content":extract[:1200]})
            return results
        except Exception:
            return []

    def _wiki_extract(self, pageid):
        try:
            url = "https://en.wikipedia.org/w/api.php"
            params = {"action":"query","format":"json","prop":"extracts","explaintext":True,"pageids":pageid}
            r = requests.get(url, params=params, headers=self.headers, timeout=8)
            if r.status_code != 200:
                return ""
            pages = r.json().get("query", {}).get("pages", {})
            page = pages.get(str(pageid), {})
            return page.get("extract", "")
        except Exception:
            return ""

    def _search_and_scrape(self, base_url, query, link_selector, text_selector=None, max_results=1):
        try:
            search_url = base_url.format(q=quote_plus(query))
            r = requests.get(search_url, headers=self.headers, timeout=8)
            if r.status_code != 200:
                return []
            soup = BeautifulSoup(r.text, "html.parser")
            links = soup.select(link_selector)
            results = []
            for a in links[:max_results]:
                href = a.get("href")
                if not href:
                    continue
                if href.startswith("/"):
                    href = self._make_absolute(base_url, href)
                content = self._fetch_article(href, text_selector)
                if content:
                    results.append({
                        "source": self._source_name(base_url),
                        "title": a.get_text(strip=True)[:120],
                        "content": content[:1200]
                    })
            return results
        except Exception:
            return []

    def _make_absolute(self, base_url, path):
        if "britannica.com" in base_url:
            return f"https://www.britannica.com{path}"
        if "w3schools.com" in base_url:
            return f"https://www.w3schools.com{path}"
        if "geeksforgeeks.org" in base_url:
            return f"https://www.geeksforgeeks.org{path}"
        return path

    def _source_name(self, base_url):
        if "britannica" in base_url:
            return "Britannica"
        if "geeksforgeeks" in base_url:
            return "GeeksforGeeks"
        if "w3schools" in base_url:
            return "W3Schools"
        return "Web"

    def _fetch_article(self, url, text_selector=None):
        try:
            r = requests.get(url, headers=self.headers, timeout=10)
            if r.status_code != 200:
                return ""
            soup = BeautifulSoup(r.text, "html.parser")
            if text_selector:
                node = soup.select_one(text_selector)
                if node:
                    return self._clean_text(node.get_text(" "))
            return self._clean_text(soup.get_text(" "))
        except Exception:
            return ""

    def build_context(self, prompt, keywords):
        query = " ".join(keywords[:4]) or prompt
        context_blocks = []
        sources = []

        if not MOCK_MODE and RAG_ENABLE_WEB:
            context_blocks.extend(self._wiki_search(query))
            context_blocks.extend(self._search_and_scrape(
                "https://www.britannica.com/search?query={q}",
                query,
                "a.search-result-title"
            ))
            context_blocks.extend(self._search_and_scrape(
                "https://www.geeksforgeeks.org/?s={q}",
                query,
                "h2.entry-title a"
            ))
            context_blocks.extend(self._search_and_scrape(
                "https://www.w3schools.com/search/search.php?q={q}",
                query,
                "a.gs-title"
            ))

        for b in context_blocks:
            sources.append(b["source"])

        if not context_blocks:
            context_blocks = [{
                "source": "Fallback",
                "title": "No web sources available",
                "content": "General ML knowledge and best practices."
            }]
            sources = ["Fallback"]

        context_text = "\n\n".join([f"{b['source']} - {b['title']}:\n{b['content']}" for b in context_blocks])
        return context_text, list(dict.fromkeys(sources))

    def generate_rag_response(self, prompt, keywords):
        context, sources = self.build_context(prompt, keywords)

        if MOCK_MODE or not self._ollama_available():
            response = f"Based on the prompt and available context, here is a concise answer: {prompt}"
            return {"response": response, "sources": sources, "timestamp": datetime.utcnow().isoformat()}

        system = "You are an ML assistant. Use the provided context to answer accurately and concisely."
        user = f"CONTEXT:\n{context}\n\nUSER PROMPT:\n{prompt}\n\nProvide a helpful response."

        try:
            content = self._ollama_chat(
                model=os.getenv("RAG_MODEL", "llama3.2:3b"),
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.2,
                num_predict=512
            )
        except Exception:
            content = f"Unable to call Ollama. Prompt was: {prompt}"

        return {"response": content, "sources": sources, "timestamp": datetime.utcnow().isoformat()}
