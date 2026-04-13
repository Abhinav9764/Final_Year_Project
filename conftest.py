"""
conftest.py
===========
Adds every agent package root to sys.path so all imports resolve
correctly in both local runs and CI without any pip install -e .
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

for sub in (
    ROOT,
    ROOT / "Data_Collection_Agent",
    ROOT / "Code_Generator" / "RAD-ML",
    ROOT / "Chatbot_Interface" / "backend",
):
    s = str(sub)
    if s not in sys.path:
        sys.path.insert(0, s)
