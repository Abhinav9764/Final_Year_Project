"""
brain/code_memory.py
====================
Persistent Experience Memory for the Code Generation Agent.
Designed to log successes, failures, and compile DPO (Direct Preference Optimization)
datasets so that local SLMs (like Ollama Qwen) can be continuously trained
on ML algorithm implementation and code design.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
import difflib

log = logging.getLogger(__name__)


class CodeExperienceMemory:
    """
    RAG-style memory and DPO dataset collector for code generation.
    """

    def __init__(self, config: dict):
        self.config = config
        
        # Path to store failure memory used for in-context RAG
        memory_dir = Path("Code_Generator/RAD-ML/brain")
        memory_dir.mkdir(parents=True, exist_ok=True)
        self.memory_path = memory_dir / "code_repair_history.json"
        
        # Path for DPO training data (SLM Fine-tuning on Qwen) 
        self.dpo_path = memory_dir / "qwen_dpo_dataset.jsonl"
        
        self.history: List[Dict] = self._load()

    def _load(self) -> List[Dict]:
        if self.memory_path.exists():
            try:
                with open(self.memory_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                log.warning("Failed to load CodeExperienceMemory: %s", e)
        return []

    def _save(self) -> None:
        try:
            with open(self.memory_path, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error("Failed to save CodeExperienceMemory: %s", e)

    def record_failure(
        self, prompt_spec: dict, failed_code: str, error_msg: str, critique: str
    ) -> str:
        """
        Record a failure in the memory database. 
        Returns an 'attempt_id' so we can link it to a success later.
        """
        import uuid
        attempt_id = str(uuid.uuid4())
        
        entry = {
            "attempt_id": attempt_id,
            "task_type": prompt_spec.get("task_type", ""),
            "prompt": prompt_spec.get("task", "") or prompt_spec.get("prompt", ""),
            "failed_code": failed_code,
            "error_msg": error_msg,
            "critique": critique,
        }
        self.history.append(entry)
        self._save()
        log.info("Recorded code failure in memory (attempt_id: %s)", attempt_id)
        return attempt_id

    def record_success_and_save_dpo(
        self, prompt_spec: dict, successful_code: str, attempt_id: Optional[str] = None
    ) -> None:
        """
        If this was previously a failure (linked by attempt_id), log a DPO pair:
        (Chosen = successful_code, Rejected = failed_code).
        This builds the training dataset for the Qwen model.
        """
        if not attempt_id:
            return  # Only log DPO if it's born from a repair
            
        # Find the failure
        failure_entry = next((e for e in self.history if e.get("attempt_id") == attempt_id), None)
        if not failure_entry:
            return
            
        prompt = (
            f"Write a {failure_entry.get('task_type')} Python application.\n"
            f"User Goal: {failure_entry.get('prompt')}"
        )
        rejected = failure_entry["failed_code"]
        chosen = successful_code
        
        dpo_entry = {
            "instruction": prompt,
            "chosen": chosen,
            "rejected": rejected,
            "critique_received": failure_entry["critique"],
        }
        
        try:
            with open(self.dpo_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(dpo_entry, ensure_ascii=False) + "\n")
            log.info("Saved DPO pair to %s for Qwen SLM tuning.", self.dpo_path.name)
        except Exception as e:
            log.error("Failed to append DPO data: %s", e)

    def get_anti_patterns(self, task_type: str, user_prompt: str) -> str:
        """
        Retrieves a formatted string of past mistakes to inject into the Qwen SLM prompt.
        Uses a simple substring / heuristic matching for now.
        """
        if not self.history:
            return ""
            
        # Very basic RAG heuristic: matching task type and shared keywords
        prompt_words = set(user_prompt.lower().split())
        
        relevant = []
        for entry in self.history:
            if entry.get("task_type") == task_type:
                entry_words = set(entry.get("prompt", "").lower().split())
                overlap = len(prompt_words.intersection(entry_words))
                if overlap > 2:
                    relevant.append(entry)
                    
        if not relevant:
            return ""
            
        # Sort by overlap DESC, take top 2
        relevant.sort(key=lambda x: len(prompt_words.intersection(set(x.get("prompt", "").lower().split()))), reverse=True)
        top_k = relevant[:2]
        
        anti_patterns = "⚠️ CRITICAL SYSTEM MEMORY - PAST FAILURES TO AVOID ⚠️\n"
        anti_patterns += "In previous attempts similar to this task, the generated code suffered from these errors:\n"
        
        for idx, entry in enumerate(top_k):
            anti_patterns += f"\n--- Past Failure {idx+1} ---\n"
            anti_patterns += f"Error Triggered: {entry['error_msg'][:300]}...\n"
            anti_patterns += f"LLM Judge Critique: {entry['critique']}\n"
            anti_patterns += "DO NOT REPEAT the mistakes mentioned in the critique.\n"
            
        return anti_patterns
