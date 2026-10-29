"""Shim: the code lives in src/exam_engine/utils/md2html.py."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
from exam_engine.utils.md2html import *  # noqa: E402,F401,F403
from exam_engine.utils.md2html import main  # noqa: E402

if __name__ == "__main__":
    main()
