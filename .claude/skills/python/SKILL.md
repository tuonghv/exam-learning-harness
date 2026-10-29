---
name: python
description: Python standards for this repo - md2html.py, the json_repair fallback in load_json.sh, and python3 heredocs embedded in *.sh and .claude/scripts. Use when writing or changing any Python here, standalone or embedded in a shell script, or when testing it.
---

# Python

Python is the language for the exam tools (`tools/examples/`), stdlib only.
Where it lives (there is no package, no venv, no pytest suite):

| Code | Runs from | Tested by |
|---|---|---|
| `md2html.py` (Markdown → print HTML) | `report_common.sh` (PDF step, never fatal) | `tests/md2html_test.sh` (links), `tests/flow_map_test.sh` (flow cards); manual check in reference "Testing a change" step 4 |
| `python3 -c` in `load_json.sh` (`json_repair` salvage) | `scan_batch.sh`, reports | `tests/load_json_test.sh` |
| `python3 - … <<'PY'` in `.claude/scripts/*.sh` | workflow gates, hooks | `.claude/tests/workflow_gates_test.sh` |
| `.claude/req/req.py`, `hook_*.py`, `task_gate.py` (requirement ledger) | UserPromptSubmit/SessionStart/Stop hooks, `docs/req/config.json` checks | `.claude/tests/req_kit_test.sh` |

## Constraints

- **No bytecode under `.claude/`:** a `.py` that another script imports (hooks import `req.py`)
  sets `sys.dont_write_bytecode = True` before the import. A throwaway test repo that copies
  `.claude/` has no `.gitignore`, so a stray `__pycache__` gets staged and `commit-check.sh` fails
  ("forbidden path staged ... bytecode"). Syntax-check with `python3 -m py_compile` only if you
  delete the `__pycache__` it leaves; test harnesses strip it after `cp -r` (both `.claude/tests`).
- **Python 3.8 floor** (this host has 3.8.10, macOS ships 3.9): no `match`,
  no `X | Y` unions or `list[int]` in evaluated annotations (use `typing` or
  `from __future__ import annotations`), no `str.removeprefix`, no `dict | dict`,
  no `zoneinfo` (3.9); for time zones, shell out with `TZ=` like
  `scheduler_common.sh`.
- **Stdlib only.** The single allowed third-party module is `json_repair`,
  and only in `load_json.sh`, which must keep working when it is missing
  (strict `jq` parse first, fallback second). Never add another `pip` dependency.
- **Embedded Python:** quote the heredoc delimiter (`<<'PY'`), pass every
  path/value as argv (`python3 - "$f" "$x" <<'PY'` → `sys.argv`), never
  interpolate shell variables into the program text. Keep the program short;
  if it grows past ~60 lines or needs its own tests, move it to a `.py` file.
- **Exit codes are the interface** to the calling shell script: `0` ok,
  non-zero with a one-line reason on stderr (`raise SystemExit("FAIL: …")`).
  Never print a traceback as the normal failure path; never exit 0 after a
  failure.
- **Untrusted input:** scan results and model output reach `md2html.py` and
  `load_json.sh`. HTML-escape all text (`html.escape`), never `eval`/`exec`/
  `pickle`, and treat a parse failure as data to report, not a crash.
- **State files** (`.claude/state/*.json`): read with `json.load`, write the
  whole document back with `indent=2` and a trailing newline (as `backlog.sh`
  does); only the owning script writes.

Prefer small functions, explicit exceptions and `pathlib`/`with open(...)`;
avoid module-level side effects in `md2html.py` (keep the `main()` guard) so a
test can import it.

## Testing

A unit test is a bash test in the repo's harness style (`unit-test` skill):
run the script or `python3 -c 'import md2html; …'` from a `mktemp -d` fixture
and assert the exit code plus an output substring. Run `tests/run_all.sh <name>`
while iterating and `tests/run_all.sh` before UNIT_TESTED.

Static check: the post-edit hook runs `py_compile` (and `ruff` if installed) on
every edited `.py`; `.claude/scripts/checks/python.sh` covers the whole repo.
Its "no pytest tests found" WARN is expected here and is not evidence of anything.
