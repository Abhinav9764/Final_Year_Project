"""
main.py
=======
RAD-ML Entry Point — orchestrates the full RL data-collection loop.

Usage:
    python main.py
    python main.py --prompt "electric vehicle battery datasets" --episodes 10
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: make sure the project root is on sys.path
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_config(path: str = "config.yaml") -> dict:
    """Load YAML config, raising a clear error if the file is missing."""
    try:
        import yaml  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "PyYAML is not installed. Run: pip install pyyaml"
        ) from exc

    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {cfg_path.resolve()}\n"
            "Make sure config.yaml exists in the project root."
        )

    with cfg_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError("config.yaml must be a YAML mapping (dict).")

    return config


def print_banner() -> None:
    """Print a startup banner using rich if available."""
    try:
        from rich.console import Console  # noqa: PLC0415
        from rich.panel import Panel  # noqa: PLC0415
        from rich.text import Text  # noqa: PLC0415

        console = Console()
        banner = Text("RAD-ML", style="bold magenta", justify="center")
        console.print(
            Panel(
                banner,
                subtitle="[dim]RL-Driven Adaptive Data Collector[/dim]",
                border_style="magenta",
            )
        )
    except ImportError:
        print("=" * 50)
        print("         RAD-ML — RL-Driven Adaptive Data Collector")
        print("=" * 50)


def run_agent(prompt: str, config: dict, num_episodes: int) -> None:
    """
    Main agent loop.

    1. Extract keywords from the prompt.
    2. For each episode:
       a. Reset environment.
       b. Agent selects actions until done.
       c. Learn from (state, action, reward, next_state) tuples.
       d. Record episode reward in EvolutionEngine.
    3. Save Q-table.
    4. Print session summary.

    Raises
    ------
    RuntimeError
        If any critical module fails to initialise.
    """
    import logging  # noqa: PLC0415

    logger = logging.getLogger(__name__)

    # --- Initialise components ---
    try:
        from brain.extractor import KeywordExtractor  # noqa: PLC0415
        from collectors.ddg_search import DDGSearchClient  # noqa: PLC0415
        from collectors.kaggle_client import KaggleClient  # noqa: PLC0415
        from core.agent import RLAgent  # noqa: PLC0415
        from core.environment import Environment  # noqa: PLC0415
        from core.evolution_engine import EvolutionEngine  # noqa: PLC0415
        from utils.data_cleaner import DataVerifier  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            f"Failed to import a required module: {exc}\n"
            "Run: pip install -r requirements.txt"
        ) from exc

    logger.info("Initialising components…")

    extractor = KeywordExtractor(config.get("nlp", {}))
    ddg_client = DDGSearchClient(config.get("collection", {}))
    kaggle_client = KaggleClient(config)
    verifier = DataVerifier(config.get("verification", {}))
    agent = RLAgent(config.get("rl", {}))
    env = Environment(ddg_client, kaggle_client, verifier, config)
    evolution = EvolutionEngine(agent, config.get("rl", {}))

    # --- Keyword extraction ---
    logger.info("Analysing prompt: '%s'", prompt)
    try:
        keyword_bundle = extractor.extract(prompt)
    except (ValueError, RuntimeError, OSError) as exc:
        raise RuntimeError(f"Keyword extraction failed: {exc}") from exc

    logger.info(
        "Keywords — primary: %s | tags: %s",
        keyword_bundle["primary"],
        keyword_bundle["tags"],
    )

    # --- RL Loop ---
    action_names = {0: "DuckDuckGo", 1: "Kaggle", 2: "Refine Keywords"}

    for episode in range(1, num_episodes + 1):
        logger.info("━━━ Episode %d / %d ━━━", episode, num_episodes)
        state = env.reset(keyword_bundle)
        episode_reward = 0.0
        done = False

        while not done:
            action = agent.choose_action(state)
            logger.info("Action chosen: %s (%d)", action_names[action], action)

            try:
                next_state, reward, done = env.step(action)
            except ValueError as exc:
                logger.error("Environment step error: %s", exc)
                break

            agent.learn(state, action, reward, next_state)
            episode_reward += reward
            state = next_state

        evolution.record_episode(episode_reward, episode)

    # --- Persist Q-table ---
    try:
        agent.save_qtable()
    except OSError as exc:
        logger.warning("Could not save Q-table: %s", exc)

    # --- Session Summary ---
    summary = evolution.summary()
    logger.info("━━━ Session Summary ━━━")
    for key, value in summary.items():
        logger.info("  %-22s: %s", key, value)

    try:
        from rich.console import Console  # noqa: PLC0415
        from rich.table import Table  # noqa: PLC0415

        console = Console()
        table = Table(title="RAD-ML Session Summary", border_style="cyan")
        table.add_column("Metric", style="bold")
        table.add_column("Value")
        for k, v in summary.items():
            table.add_row(k.replace("_", " ").title(), str(v))
        console.print(table)
    except ImportError:
        pass  # Summary already logged above


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="RAD-ML: RL-Driven Adaptive Data Collector"
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Research topic / prompt for the agent.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to the config YAML file (default: config.yaml).",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=None,
        help="Number of RL episodes (overrides config.yaml value).",
    )
    args = parser.parse_args()

    print_banner()

    # Load config
    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError, ImportError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    # Setup logging first
    from utils.logger import setup_logger  # noqa: PLC0415
    setup_logger(config.get("logging", {}))
    import logging  # noqa: PLC0415
    logger = logging.getLogger(__name__)

    # Number of episodes
    num_episodes: int = (
        args.episodes
        or config.get("rl", {}).get("num_episodes", 20)
    )

    # Prompt
    if args.prompt:
        prompt = args.prompt
    else:
        try:
            prompt = input("Enter your research topic/prompt: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted by user.")
            sys.exit(0)

    if not prompt:
        print("[ERROR] Prompt cannot be empty.", file=sys.stderr)
        sys.exit(1)

    # Run
    try:
        run_agent(prompt, config, num_episodes)
    except RuntimeError as exc:
        logger.critical("Agent failed: %s", exc)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning("Agent interrupted by user. Exiting.")
        sys.exit(0)


if __name__ == "__main__":
    main()
