import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from generator.code_gen_factory import CodeGenFactory, WORKSPACE_APP_DIR
from engines.ml_engine.sagemaker_handler import SageMakerHandler
from intent_classifier import classify_intent


def main():
    parser = argparse.ArgumentParser(description="Generate code, train on SageMaker, and deploy locally.")
    parser.add_argument("--prompt", type=str, required=True, help="User prompt describing the desired application.")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to config.yaml for LLM and AWS settings.")
    parser.add_argument("--dataset", type=str, default="collected_dataset.csv", help="Path to the collected CSV dataset.")
    args = parser.parse_args()

    # Load config
    try:
        import yaml
        with open(args.config, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
    except Exception as exc:
        print(f"[ERROR] Failed to load config: {exc}", file=sys.stderr)
        sys.exit(1)

    # Intent classification
    intent = classify_intent(args.prompt)
    mode = intent.get("mode", "ml")
    features = intent.get("features", [])
    target_column = intent.get("target_column", "")

    engine_meta = {"features": features, "target_column": target_column}
    data_source_info = {}

    # Code generation
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

    # Write generated app to workspace
    factory.write_to_workspace(bundle, app_dir=WORKSPACE_APP_DIR)
    print(f"Generated Streamlit app written to {WORKSPACE_APP_DIR}")

    # Prepare dataset path (should be uploaded already by Data Collection Agent)
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"[ERROR] Dataset file not found: {dataset_path}", file=sys.stderr)
        sys.exit(1)

    # Upload dataset to S3 if not already done (the Data Collection Agent may have uploaded)
    # Here we assume the S3 URI is known via config
    aws_cfg = cfg.get('aws', {})
    bucket = aws_cfg.get('s3_bucket')
    region = aws_cfg.get('region')
    s3_uri = None
    if bucket:
        s3_key = f"datasets/{dataset_path.name}"
        s3_uri = f"s3://{bucket}/{s3_key}"
        # Upload if needed
        try:
            import boto3
            s3 = boto3.client('s3', region_name=region) if region else boto3.client('s3')
            s3.upload_file(str(dataset_path), bucket, s3_key)
            print(f"Uploaded dataset to {s3_uri}")
        except Exception as exc:
            print(f"[WARNING] Could not upload dataset to S3 (may already exist): {exc}")
    else:
        print("[WARNING] No S3 bucket configured; proceeding with local path for SageMaker mock mode.")
        s3_uri = str(dataset_path)

    # SageMaker training
    handler = SageMakerHandler(cfg)
    try:
        meta = handler.run_training(s3_input_uri=s3_uri, target_column=target_column or "target")
        print("SageMaker training completed. Endpoint:", meta.get('endpoint_name'))
    except Exception as exc:
        print(f"[ERROR] SageMaker training failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # Local deployment (run Streamlit)
    print("To launch the generated app locally, run:\n    streamlit run " + str(WORKSPACE_APP_DIR / "app.py"))


if __name__ == "__main__":
    main()
