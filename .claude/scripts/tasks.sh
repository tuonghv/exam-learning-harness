#!/usr/bin/env bash
# Per-task workflow state (REQ-0060, phase 96): list | sync | scope | migrate | status | hold | resume | show.
# stale | inputs | question (96.13, 96.15). Logic lives in _tasks.py.
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<EOF
Usage:
  $(basename "$0") list                                   # mode, max_active, active tasks
  $(basename "$0") sync                                   # rewrite the task.json view (schema 2)
  $(basename "$0") scope <TASK-N> [--set g1,g2|--add g1,g2|--from-design]
  $(basename "$0") migrate                                # legacy task.json -> task.<T>.json + view
  $(basename "$0") status                                 # C7 view, <=25 lines
  $(basename "$0") recover                                # break dead locks, remove tmp litter, print resume lines
  $(basename "$0") hold <T> --reason R [--next N] | resume <T> | show <T>
  $(basename "$0") stale <T>                              # rc 0 clean, rc 4 stale (C5)
  $(basename "$0") inputs <T> [--set p1,p2 | --rehash --reason R]
  $(basename "$0") question <T> [--set N | --answer | --decide TEXT --reason R]
  $(basename "$0") lead <T>                               # main only: new lead generation + brief (refused at gen 3)
  $(basename "$0") set <T> --merge work/<T>/x.json        # whitelisted keys only
  $(basename "$0") checkpoint <T> [--done X] [--next N]
  $(basename "$0") commit <T> <msgfile> --log <entryfile> -- <paths>   # scoped commit under tasks-commit.lock
  $(basename "$0") commit <T> <msgfile> [--log -] -- <paths>            # no phase-log entry (one-call commit helper)
  $(basename "$0") workable [--exclude T]                 # queued tasks a stuck lead may pick (WORKABLE/SKIP rows)
  $(basename "$0") autohold <T> <Q-id>                    # main/lead: hold T on its due user question, pick next, commit both
  $(basename "$0") keepalive [--watch]                    # WAIT/DUE/STALL/OK verdict (rc 4 on STALL/DUE); --watch polls ($0)
  $(basename "$0") nextpick                               # Stop hook: stdin JSON -> systemMessage/decision (rc 0 always)
  $(basename "$0") set <T> --state S                                  # same or next state (rollback to IMPLEMENTING ok)
EOF
  exit 1
}

cmd="${1:-}"; shift || true
case "$cmd" in
  list|sync|migrate|recover) exec python3 "$SCRIPT_DIR/_tasks.py" "$cmd" "$@" ;;
  scope) [ $# -ge 1 ] || usage; exec python3 "$SCRIPT_DIR/_tasks.py" scope "$@" ;;
  status) exec python3 "$SCRIPT_DIR/_tasks.py" status ;;
  hold|resume|show) [ $# -ge 1 ] || usage; exec python3 "$SCRIPT_DIR/_tasks.py" "$cmd" "$@" ;;
  stale|inputs|question) [ $# -ge 1 ] || usage; exec python3 "$SCRIPT_DIR/_tasks.py" "$cmd" "$@" ;;
  lead|set|checkpoint|commit) [ $# -ge 1 ] || usage; exec python3 "$SCRIPT_DIR/_tasks.py" "$cmd" "$@" ;;
  workable) exec python3 "$SCRIPT_DIR/_tasks.py" workable "$@" ;;
  autohold) [ $# -ge 1 ] || usage; exec python3 "$SCRIPT_DIR/_tasks.py" autohold "$@" ;;
  keepalive|nextpick) exec python3 "$SCRIPT_DIR/_tasks.py" "$cmd" "$@" ;;
  *) usage ;;
esac
