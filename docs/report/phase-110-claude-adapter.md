# Phase 110 – Claude adapter (`src/exam_engine/adapters/claude.py`)

## Findings

### F001 – [MEDIUM] `_classify` matches bare digits and common words, turning ordinary failures into run-stopping classes

- File: src/exam_engine/adapters/claude.py
- Lines: 43-51, 132
- Issue: Substring tests for "401", "429", "500", "service", "login", "connection" run over stderr plus the result text, or the whole stdout envelope when `result` is not a string. Any hit yields a class in `engine.BLOCKING`, which raises `Stop`.
- Case: `is_error` result "Prompt is too long: 215003 tokens" contains "500" -> "service"; a raw envelope containing `service_tier` or a matching digit run does the same.
- Fix: Match status codes with word boundaries (`\b401\b`, `\b429\b`, `\b50[0234]\b`), replace bare "service"/"login" with specific phrases, and at line 132 never classify raw `out`; use `err` only when `res` is not a string.

### F002 – [MEDIUM] A brace in prose before the JSON object makes `extract_json` fail

- File: src/exam_engine/adapters/claude.py
- Lines: 175-177, 187-192
- Issue: `_objects` finds the one valid object, but it is used only when `len(objs) > 1`. The fallback slices from the first `{` to the last `}`, which is not valid JSON when prose contains braces.
- Case: Unfenced reply `Since \frac{1}{2} > 0. {"answer": "A"}` returns `(None, "no valid JSON object found")`.
- Fix: Before the final return, call `_objects(text)`; if exactly one dict is found (and it validates when `schema` is given), return it.

### F003 – [LOW] Two fenced objects are rejected before the schema retraction rule runs

- File: src/exam_engine/adapters/claude.py
- Lines: 172-177
- Issue: The `len(fences) > 1` return precedes the `schema` branch, whose comment says it handles several objects "fenced or not". That branch is unreachable for replies with two or more fences.
- Case: Reply with a first fenced object, "Correction:", then a second fenced valid object and `schema=SOLVE_OUT` returns "more than one code fence".
- Fix: Move the `schema is not None` block above the fence-count check, or apply the fence-count rejection only when `schema is None` or `_objects` yields fewer than two objects.

### F004 – [LOW] Subprocess text I/O uses the locale encoding and encoding errors are uncaught

- File: src/exam_engine/adapters/claude.py
- Lines: 117-122
- Issue: `universal_newlines=True` without `encoding` encodes the prompt and decodes stdout with the locale codec. `UnicodeEncodeError`/`UnicodeDecodeError` are `ValueError`, not `OSError`, so they escape `_run` instead of returning a `Call`.
- Case: Non-UTF-8 locale (e.g. `LANG=en_US.ISO-8859-1`) with a Vietnamese prompt, or invalid UTF-8 bytes in CLI output.
- Fix: Pass `encoding="utf-8", errors="replace"` to `runner`, and add `except ValueError` returning `_bad("other", ...)`.

### F005 – [LOW] Exit 0 with unparseable stdout is reported as "empty result"

- File: src/exam_engine/adapters/claude.py
- Lines: 96-99, 130, 134-135
- Issue: When `_envelope` returns None or a non-dict (non-JSON stdout, a JSON list, or a stream with no `result` line), `res` is None and the call is classed "empty" with reason "empty result"; stdout and stderr are discarded.
- Case: CLI exits 0 after printing a warning line before the JSON envelope; the log shows "empty result" although output was present.
- Fix: If `env` is not a dict and `out.strip()` is non-empty, return `_bad("other", "unparseable output: " + err + " " + out, dur)`; keep "empty" for a dict envelope with blank `result`.

### F006 – [LOW] `prompt` and `model` are not validated before the subprocess call

- File: src/exam_engine/adapters/claude.py
- Lines: 63-64, 112-122
- Issue: `prompt=None` is passed as `input=None`, so the child inherits the parent's stdin and blocks until the timeout or consumes the parent's input. `model=None` puts None in `argv`, raising `TypeError`, which is not caught by `except OSError`.
- Case: `run_claude(None, model="claude-x-1", timeout_s=600)` or `run_claude("q", model=None, timeout_s=60)`.
- Fix: At the top of `_run`, return `_bad("other", "prompt/model must be a non-empty str", 0.0)` unless both are non-empty strings.

## Summary

- Total findings: 6
- Critical: 0
- High: 0
- Medium: 2
- Low: 4
