"""Shim: the code lives in src/exam_engine/core/schema.py (schemas in schemas/*.json)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
from exam_engine.core.schema import *  # noqa: E402,F401,F403
from exam_engine.core.schema import QA_OUT, RESULT, SOLVE_OUT  # noqa: E402,F401
