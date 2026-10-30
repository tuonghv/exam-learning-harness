#!/usr/bin/env python3
"""UserPromptSubmit hook: save the prompt verbatim as RAW-xxxxx and inject a short ledger brief.
Never blocks the prompt; any error exits 0 silently."""
import json, re, sys
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ in .claude/ (commit-check rejects bytecode)
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import req
    data = json.load(sys.stdin)
    if not req.DATA.exists():
        sys.exit(0)
    prompt = (data.get("prompt") or "").strip()
    min_chars = int(req.config().get("capture_min_chars", 25))
    # skip bare slash commands without arguments
    bare_cmd = re.fullmatch(r"/[\w:.-]+", prompt or "")
    # skip harness events that arrive as prompts (task notifications, subagent hand-backs): no user words
    system_event = re.match(r"\s*(<task-notification>|<agent-message\b|\[SYSTEM NOTIFICATION)", prompt or "")
    parts = []  # one output line per prompt (REQ-0006 AC4: hook context stays small)
    if prompt and not bare_cmd and not system_event:
        if len(prompt) >= min_chars:
            rid = req.capture_raw(prompt, data.get("session_id", ""))
            parts.append(f"[REQ] prompt saved as {rid}. Before you stop: triage it (skill req-intake): "
                         f"link to a REQ/EPIC, create one, or `raw ignore {rid} --reason ...`")
        else:
            # short acks ("ok", "run the real migration") are kept on record, already IGNORED, no triage (RAW-00380)
            rid = req.capture_raw(prompt, data.get("session_id", ""), f"short ack (auto, under {min_chars} chars)")
            parts.append(f"[REQ] short prompt saved as {rid} (auto-ignored; link it if it holds a decision)")
    parts += [x for x in req.brief_text(limit=4).split("\n") if x]
    print(" | ".join(parts))
except SystemExit:
    raise
except Exception:
    sys.exit(0)
