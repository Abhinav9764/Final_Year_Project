"""
shared/prompt_parser.py
=======================
Global import shim — re-exports the enhanced PromptParser from
Data_Collection_Agent/brain/prompt_parser.py so any agent in the
RAD-ML project can use a single, unified import:

    from shared.prompt_parser import PromptParser

This is the canonical import point across all agents.
"""
from __future__ import annotations
import sys
from pathlib import Path

# Ensure the Data_Collection_Agent package is on the path
_PROJ_ROOT = Path(__file__).resolve().parent.parent
_DCA_ROOT  = _PROJ_ROOT / "Data_Collection_Agent"
for _p in (str(_PROJ_ROOT), str(_DCA_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dca_brain.prompt_parser import PromptParser  # noqa: E402, F401

__all__ = ["PromptParser"]
