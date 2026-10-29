#!/usr/bin/env bash
# context_pack.sh <dir> - write the inbox-triage agent's read-only project context (phase 71.8):
#   project.md        the project's CLAUDE.md (purpose, commands, terms, rules)
#   requirements.md   ReqKit's generated index (every REQ with status and title)
#   req-intake.md     ReqKit's req-intake skill (how records become requirements)
#   skills.md         every project skill and agent: "name: description"
#   reference-toc.md  section headings of docs/guide/toolkit-reference.md
# Docs only (never plans/, results/ or REPOS_ROOT); a missing source is skipped. Env: REQ_DIR.
set -euo pipefail
OUT="${1:?usage: context_pack.sh <dir>}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
mkdir -p "$OUT"
cpy() { [ ! -f "$REPO/$1" ] || cp "$REPO/$1" "$OUT/$2"; }
cpy CLAUDE.md project.md
cpy "${REQ_DIR:-docs/req}/INDEX.md" requirements.md
cpy .claude/skills/req-intake/SKILL.md req-intake.md
python3 - "$REPO" > "$OUT/skills.md" <<'PY'
import glob, os, re, sys
repo = sys.argv[1]
print("# Project skills and agents (name: description)\n")
for kind, pat in (("skill", ".claude/skills/*/SKILL.md"), ("agent", ".claude/agents/*.md")):
    for p in sorted(glob.glob(os.path.join(repo, pat))):
        m = re.match(r"^---\n(.*?)\n---", open(p, encoding="utf-8").read(), re.S)
        meta = dict(l.split(":", 1) for l in (m.group(1).splitlines() if m else []) if ":" in l)
        name = meta.get("name", os.path.basename(os.path.dirname(p))).strip()
        print(f"- {kind} `{name}`: {meta.get('description', '').strip()}")
PY
if [ -f "$REPO/docs/guide/toolkit-reference.md" ]; then
  { echo "# docs/guide/toolkit-reference.md sections"; grep -E '^#{1,3} ' "$REPO/docs/guide/toolkit-reference.md"; } > "$OUT/reference-toc.md"
fi
