"""Shim: the code lives in src/exam_engine/adapters/claude.py."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
from exam_engine.adapters.claude import *  # noqa: E402,F401,F403
from exam_engine.adapters.claude import _classify  # noqa: E402,F401
