import sys
import os
from pathlib import Path
import pandas as pd

# Add RAD-ML to path
sys.path.insert(0, str(Path("c:/Users/sabhi/OneDrive/Documents/Final_Year_Project/Code_Generator/RAD-ML").resolve()))

from engines.ml_engine.data_preprocessor import DataPreprocessor

csv_path = "test_movies.csv"

df = pd.DataFrame({
    "User Id": [1, 2],
    "Movie Id": [101, 102],
    "Movie Title": ["A", "B"],
    "Genre": ["Action", "Comedy"],
    "Language": ["EN", "HI"],
    "Release Year": [2020, 2021],
    "Director": ["Dir A", "Dir B"],
    "Sentiment": [1, 0]
})
df.to_csv(csv_path, index=False)

cfg = {"aws": {"s3_bucket": "test", "region": "us-east-1"}}
preprocessor = DataPreprocessor(cfg)
meta = preprocessor.process(
    csv_path=csv_path,
    target_column="Sentiment",
    user_prompt="Build a ML model for movie prediction system, that predicts the movies based on the actors and actresses, genre, and language"
)

print("Target Column:", meta["target_column"])
print("Features Kept:", meta["features"])

os.remove(csv_path)
