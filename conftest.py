"""
conftest.py
===========
Pytest configuration — adds the project root to sys.path so all
'brain', 'core', 'collectors', 'utils' packages resolve correctly
in both local runs and GitHub Actions CI.
"""

import sys
from pathlib import Path

# Insert project root at the front of sys.path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
