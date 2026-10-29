#!/usr/bin/env bash
# PreCompact: warn when work is uncommitted, so a compaction never drops state
# that lives only in the conversation. Checks the whole toolkit (scripts,
# prompt, tests, docs, .claude) except manifest.json, which scans rewrite and
# the workflow never commits, and the req-kit files every prompt rewrites (RAW
# captures, INDEX.md, STATE.json): they are already on disk, and flagging them
# would warn on every auto-compaction. Pairs with the context-compaction skill boundary.
# Never blocks (always exit 0): a blocked compaction at a full context leaves /clear as the
# only way out and loses the conversation (RAW-00290..00294, 2026-10-02). The dirty list goes
# to stdout so the compaction keeps it.
set -uo pipefail
ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$ROOT" || exit 0
git rev-parse --git-dir >/dev/null 2>&1 || exit 0
# REQ-0060 multi (96.12): several tasks = keep every task's state and pending questions across the compaction
if ls "$ROOT"/.claude/state/task.TASK-*.json >/dev/null 2>&1; then
  bash "$ROOT/.claude/scripts/tasks.sh" status 2>&1
  for tf in "$ROOT"/.claude/state/task.TASK-*.json; do
    tid="$(basename "$tf" .json)"; tid="${tid#task.}"
    wf="$(bash "$ROOT/.claude/scripts/workflow-check.sh" --task "$tid" 2>&1)" || printf '%s\n' "$wf" | grep -E '^FAIL'
  done
  bash "$ROOT/.claude/scripts/task_checkpoint.sh" brief 2>/dev/null || true
fi
dirty="$(git status --porcelain -- . ':!manifest.json' ':!docs/req/raw' ':!docs/req/INDEX.md' ':!docs/req/STATE.json')"
[ -z "$dirty" ] && exit 0
echo "Compacting with uncommitted work - after compaction, commit the transition (commit skill) and set task.json 'next':"
echo "$dirty"
exit 0
