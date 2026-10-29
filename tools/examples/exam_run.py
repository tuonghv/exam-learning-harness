"""Shim: the code lives in src/exam_engine (cli.py, engine.py); same flags."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
from exam_engine.adapters import claude as exam_llm  # noqa: E402,F401
from exam_engine.cli import solve_main as main  # noqa: E402
from exam_engine.engine import Runner, Stop, run  # noqa: E402,F401
if __name__ == "__main__":
    sys.exit(main())
