"""Shim: the code lives in src/exam_engine/pipeline/scorer.py."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
from exam_engine.pipeline.scorer import match, score_file  # noqa: E402,F401
from exam_engine.pipeline.scorer import score_main as main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
