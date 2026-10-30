#!/usr/bin/env bash
# SessionStart: runs session-start-body.sh and caps its stdout at 2000 bytes (REQ-0006 AC2),
# so state growth can never flood the context. Never blocks: always exits 0.
HERE="$(cd "$(dirname "$0")" && pwd)"
MAX="${SESSION_START_MAX_BYTES:-2000}"
bash "$HERE/session-start-body.sh" 2>/dev/null | python3 -c '
import sys
mx = int(sys.argv[1])
raw = sys.stdin.buffer.read()
if len(raw) <= mx:
    sys.stdout.buffer.write(raw)
else:
    note = b"\n[truncated: SessionStart output capped at %d bytes; run .claude/scripts/status.sh]\n" % mx
    head = raw[:mx - len(note)]
    cut = head.rfind(b"\n")
    sys.stdout.buffer.write((head[:cut] if cut > 0 else head) + note)
' "$MAX"
exit 0
