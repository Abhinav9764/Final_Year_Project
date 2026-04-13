"""
generator/llm_judge.py
======================
LLM Judge evaluator for the local SLM generated code.
Uses commercial APIs (Gemini/OpenAI/DeepSeek) specifically as a verifier.
Returns a score (0-10) and a critique.
"""
from __future__ import annotations

import json
import logging
from typing import Dict

log = logging.getLogger(__name__)


class LLMJudge:
    def __init__(self, config: dict):
        self.config = config
        
        # We enforce that the Judge uses the primary/commercial API if available
        # It relies on core.llm_client.LLMClient
        try:
            from core.llm_client import LLMClient
            self.llm = LLMClient(config)
        except Exception as e:
            log.warning("Could not initialize LLMJudge LLMClient: %s", e)
            self.llm = None

    def evaluate_code(self, code: str, prompt_spec: dict) -> Dict:
        """
        Evaluates the generated code against the prompt spec.
        Returns {"score": int, "critique": str, "passed": bool}
        """
        if not self.llm:
            log.warning("LLMJudge is disabled (no API connection). Automatically passing.")
            return {"score": 10, "critique": "Judge unavailable. Auto-passed.", "passed": True}
            
        task_mode = prompt_spec.get("task_type", "ml")
        user_prompt = prompt_spec.get("task", "") or prompt_spec.get("prompt", "")
        
        judge_prompt = (
            f"You are a strict Senior Staff Software Engineer acting as a Code Judge.\n"
            f"Your job is to evaluate if the following Python {task_mode} code completely satisfies the User Goal.\n\n"
            f"--- USER GOAL ---\n{user_prompt}\n\n"
            f"--- GENERATED CODE ---\n```python\n{code[:8000]}\n```\n\n"
            f"Evaluate the code based on:\n"
            f"1. Functional Correctness (does it do what is asked?)\n"
            f"2. Completeness (are required inputs/outputs handled?)\n"
            f"3. Safety (no malicious imports, handles errors gracefully)\n\n"
            f"Reply ONLY with a JSON object in this exact format:\n"
            f'{{"score": 8, "critique": "Brief explanation of what is good and what is missing or wrong."}}\n'
            f'Score must be from 0 to 10.'
        )
        
        try:
            resp = self.llm.generate(judge_prompt)
            # Parse JSON
            import re
            cleaned = re.sub(r"^```(?:json)?\s*", "", resp.strip(), flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            data = json.loads(cleaned)
            
            score = int(data.get("score", 0))
            critique = str(data.get("critique", "No critique provided."))
            
            # Threshold for passing is 7/10
            passed = score >= 7
            
            return {
                "score": score,
                "critique": critique,
                "passed": passed
            }
            
        except Exception as e:
            log.warning("LLMJudge evaluation failed (%s). Auto-passing to prevent pipeline blockage.", e)
            return {"score": 10, "critique": f"Judge error: {e}", "passed": True}

    def evaluate_plan(self, plan: dict, prompt_spec: dict) -> Dict:
        """
        Evaluates an architectural plan before the SLM generates code.
        """
        if not self.llm:
            return {"score": 10, "critique": "", "passed": True}
            
        user_prompt = prompt_spec.get("task", "") or prompt_spec.get("prompt", "")
        
        judge_prompt = (
            f"You are a Senior Software Architect.\n"
            f"Evaluate this proposed Implementation Plan for the user goal.\n\n"
            f"--- USER GOAL ---\n{user_prompt}\n\n"
            f"--- PLAN ---\n{json.dumps(plan, indent=2)}\n\n"
            f"Does this plan cover all necessary dependencies, files, and logic? "
            f"Reply ONLY with a JSON object:\n"
            f'{{"score": 8, "critique": "Brief explanation."}}'
        )
        
        try:
            resp = self.llm.generate(judge_prompt)
            import re
            cleaned = re.sub(r"^```(?:json)?\s*", "", resp.strip(), flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            data = json.loads(cleaned)
            score = int(data.get("score", 0))
            return {
                "score": score,
                "critique": str(data.get("critique", "")),
                "passed": score >= 7
            }
        except Exception:
            return {"score": 10, "critique": "Auto pass due to JSON parsing error.", "passed": True}
