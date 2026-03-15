import argparse
import logging
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intent_classifier import classify_intent
from generator.code_gen_factory import CodeGenFactory
from generator.code_gen_factory import WORKSPACE_APP_DIR


def main():
    parser = argparse.ArgumentParser(description="Generate Streamlit app code based on user prompt with intent classification.")
    parser.add_argument("--prompt", type=str, required=True, help="User prompt describing the desired application.")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to config.yaml for LLM settings.")
    args = parser.parse_args()

    # Load config
    try:
        import yaml
        with open(args.config, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
    except Exception as exc:
        print(f"[ERROR] Failed to load config: {exc}", file=sys.stderr)
        sys.exit(1)

    # Classify intent
    intent = classify_intent(args.prompt)
    mode = intent.get("mode", "ml")
    features = intent.get("features", [])
    target_column = intent.get("target_column", "")

    # Prepare engine meta (features, target column) for prompt building
    engine_meta = {"features": features, "target_column": target_column}
    data_source_info = {}  # No specific data source info needed for generation

    factory = CodeGenFactory(cfg)
    try:
        bundle = factory.generate(
            mode=mode,
            engine_meta=engine_meta,
            data_source_info=data_source_info,
            user_prompt=args.prompt,
            prev_error=None,
        )
    except Exception as exc:
        print(f"[ERROR] Code generation failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # Write generated bundle to workspace
    factory.write_to_workspace(bundle, app_dir=WORKSPACE_APP_DIR)
    print(f"Generated code written to {WORKSPACE_APP_DIR}")


if __name__ == "__main__":
    main()
