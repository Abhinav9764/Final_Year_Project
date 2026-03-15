"""
engines/chatbot_engine/prompt_engineer.py — Chatbot System Prompt Manager
===========================================================================
Generates and manages system prompt templates for the local SLM used
in the chatbot RAG pipeline.

Adapts the prompt based on:
  - RAG context quality (doc count, average length)
  - Conversation turn (first vs. follow-up)
  - Topic domain (extracted from Router keywords)
"""

from __future__ import annotations

import logging
from typing import List

log = logging.getLogger(__name__)


# ── Base Templates ────────────────────────────────────────────────────────────
_BASE_SYSTEM = """\
You are a helpful, accurate, and concise AI assistant.
You have access to a curated knowledge base built from recent web articles.
Always ground your answers in the provided context.
If the context does not contain enough information, say so honestly.
Never make up facts or hallucinate sources.
"""

_RAG_SYSTEM = """\
You are a domain-expert AI assistant with access to a private knowledge base.
Use ONLY the following retrieved context to answer the user's question.
If the answer is not in the context, respond with:
"I could not find that information in my knowledge base."

Context:
{context}
"""

_TOPIC_ADDENDUM = {
    "climate change":   "Focus on IPCC-aligned, peer-reviewed scientific facts.",
    "finance":          "Provide balanced information; avoid financial advice.",
    "medical":          "Always recommend consulting a qualified medical professional.",
    "legal":            "Remind users that this is not legal advice.",
    "technology":       "Prefer practical, up-to-date technical explanations.",
}


class PromptEngineer:
    """
    Generates optimised system prompts for the chatbot SLM.

    Args:
        cfg: Full config dict.
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg

    # ── Public API ────────────────────────────────────────────────────────────
    def build_system_prompt(
        self,
        keywords:  List[str] = None,
        doc_count: int = 0,
        context:   str = "",
    ) -> str:
        """
        Build a complete system prompt for the SLM.

        Args:
            keywords:  Router keywords (used to pick domain-specific addendums).
            doc_count: Number of RAG documents indexed (quality signal).
            context:   Retrieved RAG context for the current query.

        Returns:
            Formatted system prompt string.
        """
        keywords = keywords or []

        if context:
            prompt = _RAG_SYSTEM.format(context=context[:3000])   # cap context length
        else:
            prompt = _BASE_SYSTEM

        # Add domain-specific addendum if detected
        addendum = self._detect_domain(keywords)
        if addendum:
            prompt += f"\n\nDomain Note: {addendum}"

        # Quality warning if few documents were collected
        if doc_count < 3:
            prompt += (
                "\n\nNote: The knowledge base is limited. "
                "Provide answers carefully and acknowledge uncertainty where appropriate."
            )

        log.debug("System prompt built (%d chars).", len(prompt))
        return prompt

    def build_user_message(self, user_input: str, turn: int = 1) -> str:
        """
        Wraps the raw user input with any turn-specific framing.

        Args:
            user_input: Raw text from the user.
            turn:       Conversation turn number.

        Returns:
            Formatted user message string.
        """
        if turn == 1:
            return f"[First question] {user_input}"
        return user_input

    def build_generation_instruction(self) -> str:
        """
        Returns a short instruction appended to the prompt when asking
        the SLM to generate a Flask app (passed to code_gen_factory).
        """
        return (
            "Generate clean, production-ready Python and HTML. "
            "Do not include any explanation outside the JSON code block."
        )

    # ── Internal ──────────────────────────────────────────────────────────────
    @staticmethod
    def _detect_domain(keywords: List[str]) -> str:
        kw_joined = " ".join(keywords).lower()
        for domain, note in _TOPIC_ADDENDUM.items():
            if domain in kw_joined:
                return note
        return ""
