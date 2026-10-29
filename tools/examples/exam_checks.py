"""Shim: det_checks in pipeline/verifier.py, safe_eval/decide in core/, score in pipeline/scorer.py."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
from exam_engine.core.decision import decide, declined  # noqa: E402,F401
from exam_engine.core.safe_eval import MAX_EXPR_LEN, safe_eval  # noqa: E402,F401
from exam_engine.pipeline.scorer import score  # noqa: E402,F401
from exam_engine.pipeline.verifier import det_checks  # noqa: E402,F401
