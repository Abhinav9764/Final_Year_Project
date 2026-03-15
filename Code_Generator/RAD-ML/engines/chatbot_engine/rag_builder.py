"""
engines/chatbot_engine/rag_builder.py — RAG Vector Index Builder
=================================================================
Converts scraped Document dicts into a searchable Chroma index using LlamaIndex.
Exposes a query() method powered by a local Ollama model 
via LlamaIndex's QueryEngine with a retrieve + re-rank pipeline.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Dict, Optional

import chromadb
from llama_index.core import Document as LlamaDocument, VectorStoreIndex, StorageContext, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.core.postprocessor import SentenceTransformerRerank

log = logging.getLogger(__name__)

Document = Dict[str, str]   # {title, url, content}

class RAGBuilder:
    """
    Build and query a Retrieval-Augmented Generation pipeline using LlamaIndex.

    Args:
        cfg: Full config dict.
    """

    def __init__(self, cfg: dict):
        self.cfg         = cfg
        vs_cfg           = cfg.get("vector_store", {})
        rt_cfg           = cfg.get("chatbot_runtime", {})
        
        self.persist_dir = Path(vs_cfg.get("persist_dir", "data/vector_store"))
        self.index_path  = self.persist_dir / "index"
        
        self.emb_model   = vs_cfg.get("embedding_model", "all-MiniLM-L6-v2")
        self.chunk_size = max(300, int(vs_cfg.get("chunk_size", 1200)))
        self.chunk_overlap = max(0, int(vs_cfg.get("chunk_overlap", 150)))
        
        # Setup LlamaIndex Settings
        Settings.chunk_size = self.chunk_size
        Settings.chunk_overlap = self.chunk_overlap
        try:
            Settings.embed_model = HuggingFaceEmbedding(model_name=self.emb_model)
        except Exception as e:
            log.warning(f"Failed to load embedding model {self.emb_model}. Using default.")
            
        self.slm_model   = cfg.get("slm_model", "phi3")
        try:
            Settings.llm = Ollama(model=self.slm_model, request_timeout=120.0)
        except Exception as e:
            log.warning("Ollama LLM init failed.")
            
        self.use_slm     = bool(rt_cfg.get("use_slm", True))
        self._index      = None
        self._query_engine = None

    # ── Public API ────────────────────────────────────────────────────────────
    def build(self, documents: List[Document]) -> None:
        """Index documents into Chroma using LlamaIndex."""
        if not documents:
            raise ValueError("Cannot build RAG index from empty document list.")

        # Data Cleaning
        llama_docs = []
        for doc in documents:
            title = str(doc.get("title", "")).strip()
            url = str(doc.get("url", "")).strip()
            content = re.sub(r"\s+", " ", str(doc.get("content", "") or "")).strip()
            if not content:
                continue

            cleaned_text = f"{title}\n{content}".strip()
            llama_docs.append(
                LlamaDocument(
                    text=cleaned_text,
                    metadata={"url": url, "title": title}
                )
            )

        if not llama_docs:
            raise ValueError("No usable text chunks available for RAG indexing.")

        # Ensure persist directory exists
        self.index_path.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB
        db = chromadb.PersistentClient(path=str(self.index_path))
        chroma_collection = db.get_or_create_collection("rag_collection")
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        # Build Index: Embeddings + Vector Database
        self._index = VectorStoreIndex.from_documents(
            llama_docs, storage_context=storage_context
        )

        log.info("LlamaIndex + Chroma RAG index built -> %d documents.", len(documents))

    def query(self, question: str, top_k: int = 10) -> str:
        """
        Answer a question using the Retrieve + Re-rank pipeline.

        Args:
            question: User's question.
            top_k:    Number of context chunks to retrieve initially.

        Returns:
            Answer string from the SLM.
        """
        if self._index is None:
            if not self.load_existing_index():
                raise RuntimeError("Vector store is not loaded.")

        if self._query_engine is None:
            # Re-ranking using sentence transformers (cross-encoder)
            try:
                reranker = SentenceTransformerRerank(
                    model="cross-encoder/ms-marco-MiniLM-L-6-v2", top_n=3
                )
                node_postprocessors = [reranker]
            except Exception as e:
                log.warning("Failed to initialize SentenceTransformerRerank. Using standard retrieval without re-ranking.")
                node_postprocessors = []

            # Retrieve -> Re-rank -> LLM
            self._query_engine = self._index.as_query_engine(
                similarity_top_k=top_k,
                node_postprocessors=node_postprocessors,
                response_mode="compact" if self.use_slm else "no_text"
            )

        try:
            response = self._query_engine.query(question)
            answer = str(response).strip()
            if answer and answer != "None" and "Empty Response" not in answer:
                return answer
            return "I could not find relevant information in the current knowledge base."
        except Exception as exc:
            log.error("RAG query failed: %s", exc)
            return "An error occurred while querying the knowledge base."

    def load_existing_index(self) -> bool:
        """Load a pre-built Chroma index from disk."""
        try:
            if not self.index_path.exists():
                return False
                
            db = chromadb.PersistentClient(path=str(self.index_path))
            chroma_collection = db.get_or_create_collection("rag_collection")
            vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
            self._index = VectorStoreIndex.from_vector_store(
                vector_store=vector_store
            )
            log.info("Loaded existing Chroma index from %s", self.index_path)
            return True
        except Exception as exc:
            log.debug("No existing index to load: %s", exc)
            return False
