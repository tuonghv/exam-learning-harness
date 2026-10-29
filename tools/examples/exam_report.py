"""Shim: the code lives in src/exam_engine/pipeline/reporter.py."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
from exam_engine.pipeline.reporter import *  # noqa: E402,F401,F403
from exam_engine.pipeline.reporter import KINDS, evidence_kind  # noqa: E402,F401
