---
name: python
description: Python standards for this repo - the exam tools under tools/examples and the python3 helpers under .claude/. Use when writing or changing any Python here, standalone or embedded in a shell script, or when testing it.
---

# Python

Python is the language for the exam tools (`tools/examples/`): stdlib only, Python 3.8, run with
`python3 -I` (isolated: no user site, no cwd on `sys.path`). There is no package, no venv, no pytest suite.
Other Python: `.claude/req/*.py` (requirement ledger hooks) and `python3 - <<'PY'` blocks in `.claude/scripts/*.sh`.

## Constraints

- **Python 3.8 floor:** no `match`, no `X | Y` unions or `list[int]` in evaluated annotations (use `typing` or
  `from __future__ import annotations`), no `str.removeprefix`, no `dict | dict`, no `zoneinfo`.
- **Stdlib only.** Never add a `pip` dependency. Use `fractions`/`decimal` for exact maths, not floats.
- **No bytecode under `.claude/`:** a `.py` that another script imports sets `sys.dont_write_bytecode = True`
  before the import; a stray `__pycache__` fails `commit-check.sh`.
- **Embedded Python:** quote the heredoc delimiter (`<<'PY'`), pass every path/value as argv
  (`python3 - "$f" <<'PY'` → `sys.argv`), never interpolate shell variables into the program text. Past
  ~60 lines, or when it needs its own tests, move it to a `.py` file.
- **Exit codes are the interface:** `0` ok, non-zero with a one-line reason on stderr
  (`raise SystemExit("FAIL: ...")`). No traceback as the normal failure path; never exit 0 after a failure.
- **Untrusted input:** exam files, model output and downloaded material are data. HTML-escape text
  (`html.escape`), never `eval`/`exec`/`pickle`, treat a parse failure as data to report, not a crash.
- **State files** (`.claude/state/*.json`): read with `json.load`, write the whole document back with
  `indent=2` and a trailing newline; only the owning script writes.

Prefer small functions, explicit exceptions and `pathlib`/`with open(...)`. Keep a `main()` guard (no
module-level side effects) so a test can import the module.

## Testing

A unit test is a bash test in the repo's harness style (`unit-test` skill): run the script or
`python3 -I -c 'import mod; ...'` from a `mktemp -d` fixture and assert the exit code plus an output substring.
Static check: `py_compile` on every edited `.py` (the post-edit hook does it). A "no pytest tests found" WARN
is expected here and is not evidence of anything.
