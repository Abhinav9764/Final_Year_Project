import yaml
import sys
import os
from pathlib import Path

# Add RAD-ML to path
sys.path.insert(0, str(Path(".").resolve()))

from generator.code_gen_factory import CodeGenFactory

with open("config.yaml", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

# Mock a failure by giving it a bad api key
cfg["deepseek"]["api_key"] = "bad"
cfg["qwen"]["hf_token"] = "bad"

factory = CodeGenFactory(cfg)
engine_meta = {
    "features": ["actors", "actresses", "genre", "language"],
    "endpoint": "mock-endpoint-movies",
    "algorithm": "XGBoost",
    "type": "sagemaker"
}

# This should trigger fallback since API keys are bad
bundle = factory.generate(
    mode="ml",
    engine_meta=engine_meta,
    data_source_info={"s3_uri": "s3://mock", "path": "local"},
    user_prompt="Build a ML model for movie prediction system, that predicts the movies based on the actors and actresses, genre, and language"
)

print(bundle.get("python", ""))
