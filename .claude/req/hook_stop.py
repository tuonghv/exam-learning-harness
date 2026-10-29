#!/usr/bin/env python3
"""Stop hook: refuse to end the turn while the ledger has hard gaps
(untriaged RAW prompts, broken references, invalid status).
Blocks at most once per stop (stop_hook_active guard). Disable with env REQ_GATE=0."""
import json, os, sys
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ in .claude/ (commit-check rejects bytecode)
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import req
    data = json.load(sys.stdin)
    if data.get("stop_hook_active") or os.environ.get("REQ_GATE") == "0" or not req.DATA.exists():
        sys.exit(0)
    _, _, _, errors, _ = req.collect()
    if errors:
        reason = ("Requirement ledger has gaps - fix before stopping:\n- " + "\n- ".join(errors[:8]) +
                  "\nThen update focus: python3 .claude/req/req.py focus --next '<next concrete step>'")
        print(json.dumps({"decision": "block", "reason": reason}))
except SystemExit:
    raise
except Exception:
    sys.exit(0)
