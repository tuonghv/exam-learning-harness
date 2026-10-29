#!/usr/bin/env python3
"""Single entry: exam.py solve|parse|verify|report|check-examples|score|prompts ...

Run as `python3 -I scripts/exam.py ...`; <repo>/src is put on sys.path explicitly.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from exam_engine.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
