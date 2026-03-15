from pathlib import Path
import sys

import yaml

# Ensure RAD-ML package roots resolve when tests run from repository root.
RAD_ML_ROOT = Path("Code_Generator/RAD-ML").resolve()
if str(RAD_ML_ROOT) not in sys.path:
    sys.path.insert(0, str(RAD_ML_ROOT))

from engines.ml_engine import sagemaker_handler as sm_mod


def test_sagemaker_mock_mode(monkeypatch):
    cfg_path = Path("Code_Generator/RAD-ML/config.yaml")
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # Keep tests deterministic and safe: never run real AWS jobs in CI/local tests.
    monkeypatch.setattr(sm_mod, "BOTO3_AVAILABLE", False)

    handler = sm_mod.SageMakerHandler(cfg)
    meta = handler.run_training(
        s3_input_uri="s3://rad-ml-datasets/collected_data/datasets/mock.csv",
        target_column="price",
    )

    assert meta.get("endpoint_name")
    assert meta.get("model_name")
    assert meta.get("job_name")
