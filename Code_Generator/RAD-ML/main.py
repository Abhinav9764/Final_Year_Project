"""
main.py — RAD-ML Code Generator V2 (Orchestrator)
===================================================
The central controller that ties every module together:
  Phase 1: Router     → detect intent (Chatbot vs. ML)
  Phase 2: Engine     → build RAG+SLM  OR  fire SageMaker Autopilot
  Phase 3: Generator  → call DeepSeek/Qwen, verify with Gemini
  Phase 4: Testing    → run generated unit tests
  Phase 5: Refinement → feed errors back to LLM, regenerate

V2 Changes:
  - Replaced DQN Agent with LLM Self-Refinement Loop
  - Removed reward system and RL-based retry strategy
  - Simplified orchestration via RefinementLoop class
"""

import os
import sys
import argparse
import logging
from pathlib import Path

import yaml

# ── Constants ────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent
CONFIG_PATH   = BASE_DIR / "config.yaml"
LOGS_DIR      = BASE_DIR / "workspace" / "logs"

LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOGS_DIR / "orchestrator.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("Orchestrator")


# ── Config Loader ─────────────────────────────────────────────────────────────
def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, "r") as f:
        cfg = yaml.safe_load(f)
    log.info("Config loaded from %s", path)
    return cfg


# ── Main Entry ────────────────────────────────────────────────────────────────
def run(user_prompt: str) -> None:
    """
    Full RAD-ML V2 code generation pipeline.

    Args:
        user_prompt: Natural-language description of what the user wants to build.
    """
    cfg = load_config()

    # Import and run the Refinement Loop
    from core.refinement_loop import RefinementLoop

    loop = RefinementLoop(cfg)
    result = loop.run(user_prompt)

    if result.get("success"):
        log.info(
            "RAD-ML V2 build complete in %d attempt(s). App: %s",
            result.get("attempts", 0),
            result.get("deploy_url", "http://localhost:5000"),
        )
        log.info("Press Ctrl+C to stop.")
        try:
            # Keep the process alive while Flask runs
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            log.info("Shutting down.")
    else:
        log.error(
            "RAD-ML V2 build failed after %d attempt(s). Error: %s",
            result.get("attempts", 0),
            result.get("error", "unknown"),
        )


# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="RAD-ML V2: Reinforcement-Assisted Development for ML"
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="User prompt / natural-language description of what to build.",
    )
    # Legacy: accept remaining positional args
    parser.add_argument("words", nargs="*", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.prompt:
        user_prompt = args.prompt.strip()
    elif args.words:
        user_prompt = " ".join(args.words).strip()
    else:
        default_prompt = (
            "Build me a chatbot that answers questions about climate change "
            "using the latest web articles."
        )
        log.warning("No prompt supplied — using default: %r", default_prompt)
        user_prompt = default_prompt

    if not user_prompt:
        log.error("Prompt cannot be empty.")
        sys.exit(1)

    run(user_prompt)
