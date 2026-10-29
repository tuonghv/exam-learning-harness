"""Shim: the code lives in src/exam_engine/pipeline/examples_check.py."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
from exam_engine.pipeline.examples_check import *  # noqa: E402,F401,F403
from exam_engine.pipeline.examples_check import main, run_checks  # noqa: E402,F401

if __name__ == "__main__":
    sys.exit(main())
