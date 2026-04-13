import sys, os
from pathlib import Path
ROOT = Path("c:/Users/sabhi/OneDrive/Desktop/RAD-ML-v8/Code_Generator/RAD-ML")
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import yaml
with open("../../config.yaml") as f:
    config = yaml.safe_load(f)

from main import run_codegen
db_results = {
    "job_id": "test_job_movie",
    "prompt": "Suggest the movies. input: rating. output: list of recommended movies",
    "spec": {
        "task_type": "clustering",  # recommendation
        "input_params": ["rating"],
        "output_description": "list of recommended movies"
    },
    "dataset": {
        "local_path": "c:/Users/sabhi/OneDrive/Desktop/RAD-ML-v8/Data_Collection_Agent/downloads/dummy_movies.csv",
        "s3_uri": "s3://dummy/dummy_movies.csv",
        "columns": ["rating", "title", "genre"],
        "row_count": 100,
        "preview_rows": [],
    }
}
Path(db_results["dataset"]["local_path"]).parent.mkdir(parents=True, exist_ok=True)
with open(db_results["dataset"]["local_path"], "w") as f:
    f.write("title,rating,genre\nMovieA,5,Action\nMovieB,4,Comedy\n")

print("Running pipeline...")
try:
    res = run_codegen(db_results, config, "test_job", lambda step, msg: print(f"[{step}] {msg}"))
    print("SUCCESS", res.keys())
except Exception as e:
    import traceback
    traceback.print_exc()
