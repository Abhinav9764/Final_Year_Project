"""
Code_Generator/RAD-ML/core/llm_client.py
========================================
Unified LLM client with automatic provider fallback.

Primary: Gemini
Fallbacks: DeepSeek, OpenAI (when configured)
"""
from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, config: dict):
        self._config = config or {}
        llm_cfg = config.get("llm", {}) or {}
        gemini_cfg = config.get("gemini", {}) or {}
        merged_cfg = {**gemini_cfg, **llm_cfg}
        self._gemini_api_key = os.getenv("GEMINI_API_KEY") or merged_cfg.get("gemini_api_key") or merged_cfg.get("api_key", "")
        self._gemini_model = merged_cfg.get("gemini_model") or merged_cfg.get("model", "gemini-2.0-flash")
        self._retries = max(1, int(merged_cfg.get("max_retries", 2)))
        self._timeout = max(1, int(merged_cfg.get("timeout_seconds", 20)))
        self._fail_fast = str(os.getenv("RADML_FAIL_FAST_LLM", "1")).strip().lower() not in {"0", "false", "no"}
        self._fast_timeout = max(1, min(self._timeout, int(merged_cfg.get("fast_timeout_seconds", 12))))
        self._fast_retries = max(1, min(self._retries, int(merged_cfg.get("fast_retries", 1))))
        self._disable_gemini = str(llm_cfg.get("disable_gemini", os.getenv("RADML_DISABLE_GEMINI", "0"))).strip().lower() in {"1", "true", "yes"}
        self._primary_provider = str(llm_cfg.get("primary_provider", "gemini")).strip().lower()
        self._gemini_client = None
        self._fallback_order = list(llm_cfg.get("fallback_order", ["deepseek", "openai"]))
        gemini_requested = (
            not self._disable_gemini
            and (
                self._primary_provider == "gemini"
                or any(str(p).strip().lower() == "gemini" for p in self._fallback_order)
            )
        )
        if gemini_requested:
            self._init_gemini()

    def _init_gemini(self) -> None:
        if not self._gemini_api_key or self._gemini_api_key.startswith("YOUR_"):
            logger.warning("Gemini API key not configured; will rely on fallbacks if available.")
            return
        try:
            import google.generativeai as genai

            genai.configure(api_key=self._gemini_api_key)
            self._gemini_client = genai.GenerativeModel(self._gemini_model)
            logger.info("LLMClient Gemini ready: %s", self._gemini_model)
        except Exception as exc:
            logger.error("Gemini init failed: %s", exc)

    def generate(self, prompt: str) -> str:
        """Generate text with provider fallback. Raises RuntimeError on total failure."""
        failures: list[str] = []

        provider_chain: list[str] = []
        if not self._disable_gemini and self._primary_provider == "gemini":
            provider_chain.append("gemini")
        elif self._primary_provider in {"deepseek", "openai"}:
            provider_chain.append(self._primary_provider)
            if not self._disable_gemini and self._primary_provider != "gemini":
                provider_chain.append("gemini")

        for fallback in self._fallback_order:
            p = str(fallback).strip().lower()
            if p and p not in provider_chain:
                if p == "gemini" and self._disable_gemini:
                    continue
                provider_chain.append(p)

        if not provider_chain:
            provider_chain = ["deepseek", "openai"]

        for provider in provider_chain:
            provider = str(provider).strip().lower()
            if provider == "gemini":
                text, err = self._run_with_retries(
                    "gemini", lambda: self._generate_with_gemini(prompt)
                )
            elif provider == "deepseek":
                text, err = self._run_with_retries(
                    "deepseek", lambda: self._generate_with_deepseek(prompt)
                )
            elif provider == "openai":
                text, err = self._run_with_retries(
                    "openai", lambda: self._generate_with_openai(prompt)
                )
            else:
                continue

            if text:
                logger.info("LLM generation succeeded using provider: %s", provider)
                return text
            if err:
                failures.append(f"{provider}={err}")

        raise RuntimeError("LLM failed across providers: " + " | ".join(failures))

    def _run_with_retries(
        self, provider: str, fn: Callable[[], str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Run one provider with timeout + retry policy."""
        timeout = self._fast_timeout if self._fail_fast else self._timeout
        retries = self._fast_retries if self._fail_fast else self._retries

        # Keep Gemini fail-fast, but allow slower fallbacks to complete.
        if provider != "gemini":
            timeout = max(timeout, 30)
            retries = max(retries, 1)
        last_exc: Exception | None = None

        for attempt in range(1, retries + 1):
            executor = ThreadPoolExecutor(max_workers=1)
            future = None
            try:
                future = executor.submit(fn)
                text = future.result(timeout=timeout)
                if not text or not str(text).strip():
                    raise RuntimeError(f"{provider} returned an empty response")
                return str(text), None
            except FutureTimeoutError as exc:
                last_exc = exc
                logger.warning("%s attempt %d/%d timed out after %ss", provider, attempt, retries, timeout)
            except Exception as exc:
                last_exc = exc
                if attempt >= retries:
                    logger.warning("%s attempt %d/%d failed: %s", provider, attempt, retries, exc)
                else:
                    wait = 2 ** attempt
                    logger.warning("%s attempt %d/%d failed: %s; retrying in %ds", provider, attempt, retries, exc, wait)
                    time.sleep(wait)
            finally:
                if future is not None and not future.done():
                    future.cancel()
                executor.shutdown(wait=False, cancel_futures=True)

        return None, str(last_exc) if last_exc is not None else f"{provider} unavailable"

    def _generate_with_gemini(self, prompt: str) -> str:
        if self._gemini_client is None:
            raise RuntimeError("Gemini is not configured")

        response = self._gemini_client.generate_content(
            prompt,
            generation_config={
                "temperature": 0.2,
                "max_output_tokens": 4096,
            },
        )
        return str(getattr(response, "text", "") or "")

    def _generate_with_deepseek(self, prompt: str) -> str:
        deepseek_cfg = self._config.get("deepseek", {}) or {}
        api_key = os.getenv("DEEPSEEK_API_KEY") or deepseek_cfg.get("api_key", "")
        model = deepseek_cfg.get("model", "deepseek-coder")
        max_tokens = int(deepseek_cfg.get("max_tokens", 4096))

        if not api_key or str(api_key).startswith("YOUR_"):
            raise RuntimeError("DeepSeek API key is not configured")

        try:
            from openai import OpenAI  # type: ignore
        except Exception as exc:
            raise RuntimeError(f"openai package required for DeepSeek provider: {exc}") from exc

        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful coding assistant."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.2,
        )
        return str(resp.choices[0].message.content or "")

    def _generate_with_openai(self, prompt: str) -> str:
        openai_cfg = self._config.get("openai", {}) or {}
        api_key = os.getenv("OPENAI_API_KEY") or openai_cfg.get("api_key", "")
        model = openai_cfg.get("model", "gpt-4.1-mini")
        max_tokens = int(openai_cfg.get("max_tokens", 4096))
        base_url = openai_cfg.get("base_url", "")

        if not api_key or str(api_key).startswith("YOUR_"):
            raise RuntimeError("OpenAI API key is not configured")

        try:
            from openai import OpenAI  # type: ignore
        except Exception as exc:
            raise RuntimeError(f"openai package missing: {exc}") from exc

        client = OpenAI(api_key=api_key, base_url=base_url or None)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful coding assistant."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.2,
        )
        return str(resp.choices[0].message.content or "")
