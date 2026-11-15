PROGRESS: COMPLETE
SKILLS: design, token-efficiency

# Phase 109 - Claude adapter fixes (draft for docs/design/phase-109-*.md)
Task: TASK-109 · REQ-0116 · Status: draft · Supersedes: none (triage phase-107-review-triage.md Fix-B)

## Premise
- 110-F001: `_classify` (claude.py:41-52) matches bare substrings. "Prompt is too long: 215003 tokens" holds "500" -> `service`
  -> engine.py:21 BLOCKING -> engine.py:99-100 Stop for the whole run. `service` also hits `service_tier` in a raw envelope
  (claude.py:132 uses whole `out` when `result` is not a str); JSON numbers (`"duration_ms": 401`) can hit digit codes.
- 110-F002: unfenced fallback (claude.py:187-191) slices first `{`..last `}`; a brace in prose (`\frac{1}{2}`) breaks it.
- Only ok calls are cached (engine.py:95-97, raw text); parse and classify run after -> no cache-key change for either item.

## Constraints
- Python 3.8 stdlib. `_objects` keeps its signature/output (used by pipeline/explain.py:160).
- Error texts for BLOCKING classes must keep matching (AC2); everything else falls to `other` (per-question, run goes on).

## Generality
Adapter-level; covers every exam kind; no exam/subject/language literal added.

## Known incidents
none (source: work/TASK-107/handoff/design-pipeline.md rows 110-F001, 110-F002; repro work/TASK-107/repro.py:17-18).

## Plan modes
- single-source plan: engine.py:313 (solve parse, schema SOLVE_OUT) and engine.py:99 (Stop on class) - both items apply.
- pipeline plan: solver.py:150, cross.py:170 (schema), verifier.py:305 + genexam/boundary/refine (schemaless) use
  109.2; every pipeline call goes through `_run` -> 109.1. No plan-specific branch; same behaviour in both.

## Design
### 109.1 `_classify` narrowing (owner: claude.py:41-52)
Current pattern -> class -> keep/narrow (test that pins it):
| Pattern | Class | Change | Kept by |
|---|---|---|---|
| "401" | auth | narrow: code regex below | words "unauthorized"/"login" in test_exam_llm.py:95 |
| "authenticat", "api key", "unauthorized", "credential" | auth | keep | test_exam_llm.py:105,120-123 |
| "login" | auth | narrow -> "/login", "please login", "log in" | test_exam_llm.py:95 ("please login") |
| "429" | rate_limit | narrow: code regex | "rate limit" in test_exam_llm.py:96 |
| "rate limit", "rate_limit", "session limit", "usage limit", "overloaded", "hit your", "-hour limit", "reached your limit", "limit reached" | rate_limit | keep (multi-word, guarded by test_explain_qa.py:154-157) | test_exam_llm.py:96-101, test_explain_qa.py:139-147 |
| "500".."504" | service | narrow: code regex | "service unavailable" in test_exam_llm.py:103 |
| "service" | service | narrow -> "service unavailable", "service_unavailable", "internal server error", "bad gateway", "gateway timeout" | test_exam_llm.py:103 |
| "unavailable" | service | narrow -> "temporarily unavailable" (+ the "service unavailable" phrase above) | test_exam_llm.py:103 |
| "connection", "network" | service | narrow -> "connection error", "connection refused", "connection reset", "network error" | none today (no test names them) |
- Digit codes: one module regex `_HTTP = re.compile(r"(?:api error|status(?: code)?|http(?:/[\d.]+)?|error)[:\s]+(401|429|50[0-4])(?!\d)")`
  on `low`, plus a leading-code form `^\s*(401|429|50[0-4])\b` (CLI stderr "429 rate limit hit"). Code 401 -> auth,
  429 -> rate_limit, 50x -> service, checked inside the same class order (auth, rate_limit, service). Real CLI form is
  "API Error: 429 {...}" / "API Error: 500 {...}".
- Class order and return values unchanged; `_run` line 132 unchanged (no `service`/bare digit left to hit the envelope).
- Interface unchanged: `_classify(blob) -> "auth"|"rate_limit"|"service"|"other"`.

### 109.2 `extract_json` unfenced fallback (owner: claude.py:147-161, 187-191)
- Refactor `_objects` body into a private generator `_scan(text)` yielding `(start, obj)` for each top-level dict
  (same loop as now: raw_decode at each `{`, ValueError -> next `{`, Recursion/MemoryError -> stop, dict-only);
  `_objects(text)` = `[o for _, o in _scan(text)]` (output identical).
- Replace lines 187-191 with: `hits = list(_scan(text))`; if `len(hits) == 1` and the prefix `text[:start]` has
  `count("{") <= count("}")` -> return `(obj, None)`; else fall to `"no valid JSON object found"`.
  - prefix-balance guard: an object nested inside an earlier broken/truncated object (`{"answers": [{"q":1}` or
    `{"a": {"b":1}, broken}`) is not returned as a fragment (old code: None; stays None).
  - two objects without schema (or schema path not taken) -> still None (test_engine_fixes_2025_qa.py:88-91,
    test_engine_fixes_2025.py:45-47).
- Unchanged: whole-text `_load` first (169-171); >1 fence rejection (172-174); schema retraction block (175-182);
  fenced-first (183-186). Old-success inputs: a slice that parsed is one object spanning first `{`..last `}`, so
  `_scan` finds exactly it at the same start with a balanced (brace-free) prefix -> identical result.

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| Real outage text not in the narrowed list (e.g. bare "ECONNRESET") | `other`, per-question error, run continues | per-question error rows instead of a Stop |
| Prose with unbalanced `{` before the object | None (as today) | malformed_output |
| Many failing `{` in a long reply | O(n * failed-decode) scan, same cost the schema path already pays | none |

## Unit tests (new, tests/unit/test_claude_fixes_109.py)
- `test_109_1_prompt_too_long_is_other`: `_classify("Prompt is too long: 215003 tokens > 200000 maximum")` -> "other".
- `test_109_1_digits_and_words_not_blocking`: each -> "other": "processed 5000 rows", "duration_ms\": 401",
  "{\"service_tier\":\"standard\",\"is_error\":true}", "uuid 1a2b-5029-...", "login form question", "network of roads",
  "connection between A and B", "image unavailable".
- `test_109_1_real_errors_keep_class`: "API Error: 401 {...authentication_error...}" -> auth; "API Error: 429 {...}" ->
  rate_limit; "API Error: 500 {\"type\":\"api_error\"}" -> service; "API Error: 529 Overloaded" -> rate_limit;
  "Connection error." -> service; "Invalid API key · Please run /login" -> auth; "status code 503" -> service.
- `test_109_1_run_with_prompt_too_long_not_blocking`: Fake(out=env("Prompt is too long: 215003 tokens > 200000
  maximum", is_error=True)) via `run_claude` -> cls not in engine.BLOCKING.
- `test_109_2_brace_in_prose_before`: `extract_json('Since \\frac{1}{2} > 0. {"answer": "A"}')` -> ({"answer":"A"}, None);
  same with `sch.SOLVE_OUT`-valid solve object and schema passed.
- `test_109_2_brace_in_prose_after`: `'{"a": 1} then the set {x}'` -> ({"a":1}, None).
- `test_109_2_inner_fragment_not_returned`: `'{"answers": [{"q": 1}'` and `'{"a": {"b": 1}, broken}'` -> (None, "no valid JSON object found").
- `test_109_2_two_objects_still_rejected`: `'{"a":1} x {"a":2}'` (no schema) -> (None, "no valid JSON object found").
- `test_109_2_objects_unchanged`: `_objects` on 3 sample texts equals pre-change list (literal expected values).
- Must stay green: test_exam_llm.py:47-66,93-124; test_explain_qa.py:137-157; test_engine_fixes_2025*.py; test_boundary.py:98.

## Verification
| Item | Command -> expected | Tier |
|---|---|---|
| 109.1 | `python3 -I work/TASK-107/repro.py` -> 110-F001 row `other` (not BUG) | $0 |
| 109.2 | same repro -> 110-F002 row `({'answer': 'A'}, None)` | $0 |
| AC5 | replay `extract_json(text, schema)` old vs new over stored replies in plans/ + work/ (main runs a $0 script) -> diff only on brace-in-prose rows | $0 |
| gate | `python3 -I tools/run_tests.py --affected` then `--fast` -> NEW 0 | $0 |

## Decisions
- Anchor digit codes to "API Error:/status/HTTP/error" or line start - rejected: drop digits entirely (loses "API Error: 500"
  bodies without words) and `\b` only (still hits `"duration_ms": 401`).
- Keep `_run` blob (claude.py:132) as is - rejected: drop `out` for dict envelopes (wider change, may hide error fields).
- Prefix-balance guard - rejected: plain "first parseable `{`" (returns fragments of truncated objects to schemaless callers
  genexam/boundary/refine that do not always validate).
- Do not add new codes/phrases beyond narrowed forms of existing ones (529 matches via "overloaded").

## Out of scope
- Other triage fixes (Fix-C..E); retry/backoff policy; `_run` envelope handling.

## Defects
- none new (110-F001, 110-F002 confirmed against claude.py:43-51 and 187-191).
