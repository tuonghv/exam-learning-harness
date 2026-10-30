#!/usr/bin/env python3
"""SessionStart hook (startup|resume|clear|compact): re-inject the ledger state.
After compaction this is what brings the requirements back into the agent's context."""
import json, sys
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ in .claude/ (commit-check rejects bytecode)
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import req
    try:
        source = json.load(sys.stdin).get("source", "")
    except Exception:
        source = ""
    if not req.DATA.exists():
        sys.exit(0)
    import io
    real_out, sys.stdout = sys.stdout, io.StringIO()
    print(f"=== Requirement ledger ({source or 'session start'}) ===")
    print(req.brief_text(limit=8))
    focus = req.state().get("focus")
    if focus:
        print("--- focus gaps ---")
        import argparse, io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            req.cmd_gaps(argparse.Namespace(id=focus))
        print(buf.getvalue().rstrip())
    print("Source of truth for WHAT to build: docs/req/. Do not rely on memory of earlier conversation.")
    if source == "compact":
        print("Context was just compacted. Do not reconstruct requirements from the summary: "
              + ("read only the focus REQ (`python3 .claude/req/req.py show %s --section Requirement,Acceptance,Design`) "
                 "and continue from its next step." % focus if focus else "run `python3 .claude/req/req.py next`."))
    text, sys.stdout = sys.stdout.getvalue(), real_out
    MAX = 1000  # REQ-0006 AC3: bounded ledger context, no matter how large the ledger is
    if len(text.encode("utf-8")) > MAX:
        text = text.encode("utf-8")[:MAX - 80].decode("utf-8", "ignore").rsplit("\n", 1)[0] \
            + "\n[truncated: run python3 .claude/req/req.py gaps]"
    print(text)
except SystemExit:
    raise
except Exception:
    sys.exit(0)
