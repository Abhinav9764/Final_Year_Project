"""
Web Content Fetcher for Enhanced RAG System
Retrieves content from reliable knowledge sources
"""

import requests
from bs4 import BeautifulSoup
import re
import json
from typing import List, Dict, Any, Optional
from urllib.parse import quote, urljoin
import time
import hashlib
import os
import pickle
from datetime import datetime, timedelta

class WebContentFetcher:
    """Fetches content from reliable web sources for RAG enhancement"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize web content fetcher
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.knowledge_sources = config.get('KNOWLEDGE_SOURCES', {})
        self.timeout = config.get('WEB_CONTENT_TIMEOUT', 10)
        self.max_length = config.get('WEB_CONTENT_MAX_LENGTH', 5000)
        self.cache_enabled = config.get('ENABLE_WEB_CACHE', True)
        self.cache_dir = config.get('WEB_CACHE_DIR', '.web_cache')
        self.cache_duration = config.get('WEB_CACHE_DURATION', 3600)
        
        # Create cache directory
        if self.cache_enabled:
            os.makedirs(self.cache_dir, exist_ok=True)
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Educational RAG Bot) Python/Requests'
        })
    
    def fetch_content(self, query: str, max_pages: int = 3) -> List[Dict[str, Any]]:
        """
        Fetch content from multiple sources
        
        Args:
            query: Search query
            max_pages: Maximum number of pages to fetch
            
        Returns:
            List of content documents
        """
        all_content = []
        
        # Sort sources by priority
        enabled_sources = {
            name: info for name, info in self.knowledge_sources.items()
            if info.get('enabled', True)
        }
        
        sorted_sources = sorted(
            enabled_sources.items(),
            key=lambda x: x[1].get('priority', 999)
        )
        
        for source_name, source_info in sorted_sources[:max_pages]:
            try:
                if source_name == 'wikipedia':
                    content = self._fetch_wikipedia(query)
                elif source_name == 'britannica':
                    content = self._fetch_britannica(query)
                elif source_name == 'infoplease':
                    content = self._fetch_infoplease(query)
                else:
                    continue
                
                if content:
                    all_content.extend(content)
                    
            except Exception as e:
                print(f"Error fetching from {source_name}: {e}")
                continue
        
        return all_content

    def fetch_content_for_queries(self, queries: List[str], max_pages: int = 3) -> List[Dict[str, Any]]:
        """
        Fetch content for multiple queries
        
        Args:
            queries: List of search queries
            max_pages: Maximum number of pages to fetch per query
            
        Returns:
            List of content documents
        """
        all_docs = []
        for query in queries:
            docs = self.fetch_content(query, max_pages)
            if docs:
                all_docs.extend(docs)
        
        # Remove duplicates based on URL
        seen_urls = set()
        unique_docs = []
        
        for doc in all_docs:
            url = doc.get('metadata', {}).get('url')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_docs.append(doc)
            elif not url:
                unique_docs.append(doc)
                
        return unique_docs
    
    def _get_cache_key(self, query: str, source: str) -> str:
        """Generate cache key for query and source"""
        key_string = f"{source}:{query}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """Get content from cache if available and valid"""
        if not self.cache_enabled:
            return None
        
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.pkl")
        
        if not os.path.exists(cache_file):
            return None
        
        try:
            with open(cache_file, 'rb') as f:
                cached_data = pickle.load(f)
            
            # Check if cache is still valid
            if datetime.now() - cached_data['timestamp'] < timedelta(seconds=self.cache_duration):
                return cached_data['content']
            else:
                # Remove expired cache
                os.remove(cache_file)
                return None
                
        except Exception as e:
            print(f"Error reading cache: {e}")
            return None
    
    def _save_to_cache(self, cache_key: str, content: List[Dict[str, Any]]):
        """Save content to cache"""
        if not self.cache_enabled:
            return
        
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.pkl")
        
        try:
            cached_data = {
                'timestamp': datetime.now(),
                'content': content
            }
            
            with open(cache_file, 'wb') as f:
                pickle.dump(cached_data, f)
                
        except Exception as e:
            print(f"Error saving to cache: {e}")
    
    def _fetch_wikipedia(self, query: str) -> List[Dict[str, Any]]:
        """
        Fetch content from Wikipedia using their API
        
        Args:
            query: Search query
            
        Returns:
            List of content documents
        """
        cache_key = self._get_cache_key(query, 'wikipedia')
        cached_content = self._get_from_cache(cache_key)
        
        if cached_content:
            print(f"Using cached Wikipedia content for: {query}")
            return cached_content
        
        content_list = []
        
        try:
            # Wikipedia API endpoint
            api_url = "https://en.wikipedia.org/w/api.php"
            
            # Search for relevant pages
            search_params = {
                'action': 'query',
                'list': 'search',
                'srsearch': query,
                'format': 'json',
                'srlimit': 3
            }
            
            response = self.session.get(api_url, params=search_params, timeout=self.timeout)
            response.raise_for_status()
            search_data = response.json()
            
            if 'query' not in search_data or 'search' not in search_data['query']:
                return content_list
            
            # Fetch content for each page
            for result in search_data['query']['search'][:2]:  # Top 2 results
                page_title = result['title']
                
                # Get page content
                content_params = {
                    'action': 'query',
                    'prop': 'extracts',
                    'exintro': True,
                    'explaintext': True,
                    'titles': page_title,
                    'format': 'json'
                }
                
                content_response = self.session.get(api_url, params=content_params, timeout=self.timeout)
                content_response.raise_for_status()
                content_data = content_response.json()
                
                # Extract content
                pages = content_data.get('query', {}).get('pages', {})
                for page_id, page_info in pages.items():
                    extract = page_info.get('extract', '')
                    
                    if extract:
                        # Clean and truncate
                        clean_content = self._clean_text(extract)
                        
                        content_list.append({
                            'content': clean_content[:self.max_length],
                            'metadata': {
                                'source': 'Wikipedia',
                                'title': page_title,
                                'url': f"https://en.wikipedia.org/wiki/{quote(page_title)}",
                                'category': 'web_content',
                                'priority': 'high',
                                'timestamp': datetime.now().isoformat()
                            }
                        })
            
            # Cache the results
            self._save_to_cache(cache_key, content_list)
            
        except Exception as e:
            print(f"Wikipedia fetch error: {e}")
        
        return content_list
    
    def _fetch_britannica(self, query: str) -> List[Dict[str, Any]]:
        """
        Fetch content from Britannica
        
        Args:
            query: Search query
            
        Returns:
            List of content documents
        """
        cache_key = self._get_cache_key(query, 'britannica')
        cached_content = self._get_from_cache(cache_key)
        
        if cached_content:
            print(f"Using cached Britannica content for: {query}")
            return cached_content
        
        content_list = []
        
        try:
            # Format query for URL
            formatted_query = query.replace(' ', '-').lower()
            url = f"https://www.britannica.com/search?query={quote(query)}"
            
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find search results
            results = soup.find_all('a', class_='font-14', limit=2)
            
            for result in results:
                article_url = urljoin('https://www.britannica.com', result.get('href', ''))
                
                if article_url:
                    # Fetch article content
                    article_response = self.session.get(article_url, timeout=self.timeout)
                    article_response.raise_for_status()
                    
                    article_soup = BeautifulSoup(article_response.content, 'html.parser')
                    
                    # Extract main content
                    content_div = article_soup.find('div', class_='topic-paragraph')
                    
                    if content_div:
                        text = content_div.get_text(strip=True, separator=' ')
                        clean_content = self._clean_text(text)
                        
                        content_list.append({
                            'content': clean_content[:self.max_length],
                            'metadata': {
                                'source': 'Britannica',
                                'url': article_url,
                                'category': 'web_content',
                                'priority': 'high',
                                'timestamp': datetime.now().isoformat()
                            }
                        })
            
            # Cache the results
            self._save_to_cache(cache_key, content_list)
            
        except Exception as e:
            print(f"Britannica fetch error: {e}")
        
        return content_list
    
    def _fetch_infoplease(self, query: str) -> List[Dict[str, Any]]:
        """
        Fetch content from Infoplease
        
        Args:
            query: Search query
            
        Returns:
            List of content documents
        """
        cache_key = self._get_cache_key(query, 'infoplease')
        cached_content = self._get_from_cache(cache_key)
        
        if cached_content:
            print(f"Using cached Infoplease content for: {query}")
            return cached_content
        
        content_list = []
        
        try:
            # Search URL
            search_url = f"https://www.infoplease.com/search?query={quote(query)}"
            
            response = self.session.get(search_url, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find article links
            articles = soup.find_all('a', class_='search-result-title', limit=2)
            
            for article in articles:
                article_url = urljoin('https://www.infoplease.com', article.get('href', ''))
                
                if article_url:
                    # Fetch article
                    article_response = self.session.get(article_url, timeout=self.timeout)
                    article_response.raise_for_status()
                    
                    article_soup = BeautifulSoup(article_response.content, 'html.parser')
                    
                    # Extract content
                    content_div = article_soup.find('div', class_='article-body')
                    
                    if content_div:
                        paragraphs = content_div.find_all('p')
                        text = ' '.join([p.get_text(strip=True) for p in paragraphs])
                        clean_content = self._clean_text(text)
                        
                        content_list.append({
                            'content': clean_content[:self.max_length],
                            'metadata': {
                                'source': 'Infoplease',
                                'url': article_url,
                                'category': 'web_content',
                                'priority': 'medium',
                                'timestamp': datetime.now().isoformat()
                            }
                        })
            
            # Cache the results
            self._save_to_cache(cache_key, content_list)
            
        except Exception as e:
            print(f"Infoplease fetch error: {e}")
        
        return content_list
    
    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text content
        
        Args:
            text: Raw text
            
        Returns:
            Cleaned text
        """
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep alphanumeric and basic punctuation
        text = re.sub(r'[^\w\s.,;:!?()\-\'\"]+', '', text)
        
        # Remove citations like [1], [citation needed]
        text = re.sub(r'\[\d+\]|\[citation needed\]', '', text)
        
        return text.strip()
    
    def fetch_specific_content(self, query: str, source: str) -> List[Dict[str, Any]]:
        """
        Fetch content from a specific source
        
        Args:
            query: Search query
            source: Source name (wikipedia, britannica, infoplease)
            
        Returns:
            List of content documents
        """
        if source == 'wikipedia':
            return self._fetch_wikipedia(query)
        elif source == 'britannica':
            return self._fetch_britannica(query)
        elif source == 'infoplease':
            return self._fetch_infoplease(query)
        else:
            return []
    
    def clear_cache(self):
        """Clear all cached content"""
        if self.cache_enabled and os.path.exists(self.cache_dir):
            for file in os.listdir(self.cache_dir):
                file_path = os.path.join(self.cache_dir, file)
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Error removing cache file {file}: {e}")
