# Phase 2 - Exam-solving pipeline
Task: TASK-002 · REQ-0008 · EPIC-003 · Status: draft (designer Nova, 2026-10-29)
Spec: `tmp/exam-solving-workflow.md`. Reference (read-only, cited only): `code-security-scanner` (CSS).

## Goal
`python3 -I tools/examples/exam_run.py <input-NNN.md> --out <dir>` takes one FORMAT.md exam through
INPUT>VALIDATE>SOLVE>QA>DECISION>SCORE>REPORT. It writes `result.json`, which is schema-valid and the
source of truth, plus `report.md` and `report.pdf`. Every question ends PASS, FAIL or UNCERTAIN, and
unresolved questions are listed. We know it works when the mocked unit tests pass ($0) and, after the
user says go, one paid run on the 2 English few-shot items writes a valid JSON file and a PDF that opens.

## Constraints
- Python 3.8 stdlib only. Run as `python3 -I`. No `json_repair`, PDF library or external renderer.
- Eval keys never reach any `claude -p` prompt: not the solver, not QA, not a retry. A key is read only
  by SCORE, after DECISION is frozen.
- Isolation: each call runs in an empty temp cwd with no tools. The harness dir holds `evals/keys/`,
  so a call that could use Read could open the keys.
- No new agents or engines. The TASK roles build this. Only main runs it with a real `claude -p`, and
  only after the user says go (roles are barred from `claude -p` by `docs/guide/exam-brief-override.md:10`).
- Input = FORMAT.md Markdown only (`examples/FORMAT.md:17-55`). Output layout mirrors the expected
  file (`FORMAT.md:57-102`).
- Depends on REQ-0002 (layout + `check_examples.py` + `score_eval.py`). The build starts after REQ-0002 (Q3).

## Known incidents
none (this harness has no `claude -p` runner yet; grep found only docs/templates samples).

## Plan modes
- Mock mode (`--mock <responses.json>`): no network, $0. Used by all unit tests and dry runs.
- Real mode: `claude -p`, paid, run only by main after the user's go (Q2).
- `--dry-run`: VALIDATE, then print the prompts and the call plan, $0. Used to show no key leaks.

## Reuse table (pattern | CSS path:line | what we build instead)
| Pattern | CSS reference | We build |
|---|---|---|
| `claude -p`, prompt on stdin, `--output-format json` | `scan_common.sh:89-111` | `exam_llm.run_claude()`: `subprocess.run(input=prompt, timeout=)`, no shell |
| Isolation flags, checked against `claude --help` | `scan_common.sh:15,56-59` | preflight reads `claude --help` and only passes flags it lists; tools set empty; cwd = `tempfile.mkdtemp()` |
| Unset parent-session env vars | `scan_common.sh:20-22` | same variable list removed from the child `env` dict |
| Timeout plus kill | `scan_common.sh:100-102` (`timeout -k 60`) | `subprocess.run(timeout=T)`; `TimeoutExpired` gives class `timeout` |
| Failure classes (blocking vs per-item) | `scan_common.sh:113-205` | `classify(rc, envelope, stderr)` gives auth/rate_limit/service (stop the run, no attempt counted) or timeout/output/exec (attempt counted) |
| Answer sits in envelope `.result`, empty gets rejected | `scan_common.sh:237-252` | `extract_json(text)`: strict `json.loads`, then one strip of a json fence or outer `{...}`, then malformed. No repair |
| Truncation check after a repair | `scan_common.sh:253-258`, `load_json.sh:18-30` | not needed: no repair. Schema validation rejects partial output |
| Cost / turns read from envelope | `scan_batch.sh:646,654`, `p0_cost.py:54` | sum `total_cost_usd` per call and stop before the next call at `--max-cost-usd` |
| Attempt cap | `config.sh:66` (`MAX_ATTEMPTS=2`) | `--max-attempts` (default 2, env `EXAM_MAX_ATTEMPTS`) per question |
| Mock claude in tests | `tests/empty_result_test.sh:38-54` (fake binary on PATH) | injected `runner` callable / `--mock` JSON; no PATH tricks, no Bash |
| Secret masking in logs | `secret_mask.py:9-38` | `exam_llm.mask()`: about 5 regexes (Bearer, `sk-ant-`, key=/token= values). Cut stderr to 200 chars, then mask |
| Report PDF | `report_common.sh:719-774` (Chrome/weasyprint), `md2html.py:277` | stdlib PDF writer that embeds a TTF (DejaVu) with Identity-H (Q1). No renderer means we write Markdown and set `pdf_skipped` |
| Orchestration entry | `scan_batch.sh:51-61` (flags, `--retry-failed`) | `exam_run.py` argparse CLI, one exam per run |

## Gap list (missing in the harness today)
1. No `claude -p` runner, classifier or cost tracking. 2. No exam parser beyond REQ-0002's checker (not built yet).
3. No result JSON schema or validator. 4. No deterministic answer checks (MC letter, ordering permutation,
numeric+unit, verbatim quote, safe arithmetic). 5. No retry/decision logic. 6. No JSON/MD/PDF report.
7. No solver or QA prompt template. 8. No mocked-LLM tests (`tools/examples/tests/` comes from REQ-0002).

## Design
### 2.1 Modules (owner: `tools/examples/`, 6 modules)
| Module | One-line interface |
|---|---|
| `exam_parse.py` | `parse_exam(path) -> dict` (header fields, instructions, passage, questions[{id,text,options}]); `validate_exam(exam) -> list[str]`. Reuses REQ-0002 `check_examples.py` section/field readers |
| `exam_schema.py` | `RESULT`, `SOLVE_OUT`, `QA_OUT` schema dicts; `validate(obj, schema) -> list[str]` (subset: type, required, enum, properties, items, additionalProperties, minimum) |
| `exam_llm.py` | `run_claude(prompt, *, model, timeout_s, runner=subprocess.run) -> Call{ok, text, cost_usd, cls, reason, duration_s}`; `extract_json(text) -> (obj or None, err)`; `mask(s) -> str` |
| `exam_checks.py` | `det_checks(q, ans, exam) -> list[Check]`; `safe_eval(expr) -> float` (ast whitelist); `decide(checks, review, ans) -> (status, reason)`; `score(ans, key_q) -> Score` (reuses `score_eval.py` matching) |
| `exam_report.py` | `write_json(result, path)` (validates first and refuses an invalid result); `to_markdown(result) -> str` (FORMAT expected layout); `write_pdf(md_lines, path, font=None) -> bool` |
| `exam_run.py` | CLI + stage loop: `run(exam_path, out_dir, cfg, llm=run_claude) -> (result, exit_code)` |
Prompt templates: `tools/examples/prompts/solve.md`, `qa.md` (not under `docs/prompts/`, per CLAUDE.md).

### 2.2 Stage flow (owner: `exam_run.run`)
1. INPUT: `parse_exam`. VALIDATE: `validate_exam` errors on no questions, a gap or duplicate in
   `## Question N`, an empty body, MC without exactly A-D, a missing required header, or an unsupported
   Mode. Any error exits 2 with no LLM call.
2. SOLVE: one call with all questions (subject-aware `solve.md`, few-shot pair for that subject if
   present, never `evals/keys`). Output must pass `SOLVE_OUT`. A question that is missing or invalid
   gets FAIL (finding `missing_in_output`).
3. QA: (a) `det_checks` in code; (b) one separate `claude -p` review (`qa.md`) over the questions that
   pass (a). It gets the question and the answer, never a key. Verdict is `agree|disagree|unsure` plus
   findings.
4. DECISION (`decide`, deterministic): FAIL if any deterministic check fails or the review says
   disagree. UNCERTAIN if the review says unsure, uncertainty.level is not `low`, or no independent
   check passed. PASS only when there is at least one independent pass (`computed`, `quote`, or later
   `key_match`), no fail, and the review agrees. An ai_review alone never yields PASS.
   Retry: re-solve only the FAIL/UNCERTAIN ids, one call per retry round, while
   `attempts < max_attempts`. The prompt gets those questions plus non-key QA findings. Questions still
   open after the last attempt get `unresolved=true` and keep their last status.
5. SCORE: only with `--key <expected.md>` (a few-shot or eval key, read from a separate path) or an
   in-input `## Rubric`. Objective: exact match through `score_eval.py`, then status FAIL with finding
   `differs_from_key` (no retry, so the key never leaks into a later call), or a check
   `key_match`=pass that can lift UNCERTAIN to PASS. With no key or rubric: `score.basis="none"`,
   points null. Points are never invented.
6. REPORT: `write_json`, then `report.md`, then `report.pdf` (or `pdf_skipped`). Exit 0 = all PASS;
   1 = any FAIL/UNCERTAIN/unresolved; 2 = invalid input/usage; 3 = blocking stop (auth, rate_limit,
   service, cost cap). On 3 a partial result.json is still written and valid: questions not done are
   UNCERTAIN with `error`.

### 2.3 Per-question JSON (`RESULT.questions[]`, owner: `exam_schema.RESULT`)
| Field | Type | FORMAT.md mapping |
|---|---|---|
| `id` | str (`"1"`) | `## Question N` |
| `answer` | str | `Final answer:` (letter, value+unit, `c-a-d-b-e`, or `Open (rubric)`) |
| `answer_text` | str, optional | Literature essay/outline body |
| `solution` | [str] | `### Solution` numbered steps |
| `explanation` | str | `### Explanation` |
| `uncertainty` | {level: low/medium/high, reason: str} | not in FORMAT (solver self-report) |
| `checks` | [{kind: computed/format/quote/key_match/ai_review, detail, result: pass/fail/unknown, independent: bool}] | `### Verification` `- Check:` lines (`ai_review` always has independent=false) |
| `verification_status` | PASS / FAIL / UNCERTAIN | `- Status: Verified` only for PASS, else `- Status: Unverified (<status>)` |
| `status_reason` | str | Verification note |
| `qa_findings` | [{source: deterministic/ai_review/score, code, message}] | report "QA findings" |
| `score` | {points: num/null, max: num/null, basis: official_key/rubric/none, detail} | `### Grading` |
| `attempts` | int >= 1 | report |
| `unresolved` | bool | report "Unresolved issues" |
| `error` | null or {cls, message} (masked) | report |
Top level: `schema_version:1`, `exam{path,subject,level,exam_type,task,mode,language}`, `run{llm: claude-p
or mock, model, max_attempts, timeout_s, max_cost_usd, cost_usd, calls, stopped: null or cls}`, `questions[]`,
`summary{pass,fail,uncertain,unresolved,points,max_points}`. `SOLVE_OUT` = {questions:[{id, answer,
answer_text?, solution, explanation, uncertainty, computed?:[{expr, expect}]}]}. `QA_OUT` = {reviews:[{id,
verdict, findings:[str]}]}.

### 2.4 Cost and safety rules (owner: `exam_llm`, `exam_run`)
- Unit tests and `--mock` make no subprocess call: the test asserts the `runner` was not the real one.
  A real run needs explicit `--real`, the user's go, and main to run it.
- Call budget: at most 1 + 2*(max_attempts) calls per run (solve + QA per round). Also `--max-cost-usd`
  (default 1.00) is checked before each call. Defaults are `--timeout 300` and `--model sonnet`; Haiku
  is not used because exam reasoning is not a simple job (CLAUDE.md).
- Keys: `--key` is opened only in SCORE. A test puts a sentinel string in the key and asserts it is
  absent from every captured prompt. `extract_json` output is never written to prompts verbatim from
  the key.
- Independence: `ai_review` checks always have `independent=false`. PASS needs a code-checked pass.
- Logs (`<out>/run.log`): per call `cls`, rc, duration, cost, prompt/answer byte sizes. No env, no
  prompt text. Stderr is cut to 200 chars and passed through `mask()`.

### 2.5 PDF (owner: `exam_report.write_pdf`, decision Q1)
Font from `EXAM_PDF_FONT` env, else the first existing path of `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`
or `/usr/share/fonts/TTF/DejaVuSans.ttf`. Parse the TTF tables `cmap` (format 4), `hmtx`, `head` and `hhea`.
Text is NFC-normalized and drawn as a Type0/CIDFontType2 font with Identity-H glyph ids, with a
ToUnicode CMap and the whole font in FontFile2. Plain wrapped lines, A4, page breaks. Math is shown
as plain text. A missing font or a codepoint with no glyph (gid 0) gives `pdf_skipped:true` plus a
`reason`, and report.md is still written.

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| Bad input (gap, empty, MC not A-D) | exit 2, no call | `ERROR: input: Question 3 missing` |
| Malformed / partial JSON | attempt counted, ids retried | finding `malformed_output`, then UNCERTAIN + unresolved |
| Timeout / exec error | attempt counted | `error.cls=timeout` |
| auth / rate_limit / service | stop, attempt not counted, partial JSON | exit 3, `run.stopped=auth` |
| Cost cap reached | stop before the next call | exit 3, `run.stopped=cost_cap` |
| Retry exhausted | last status kept, `unresolved=true` | report "Unresolved issues" table |
| No font | Markdown only | `pdf_skipped: no DejaVu font` |

## Unit tests (tests first; `tools/examples/tests/test_exam_*.py`, mocked LLM only)
1. correct: mock answer A, key A, computed or format pass, review agree -> PASS, score 1/1.
2. incorrect: mock B, key A -> FAIL `differs_from_key`, score 0, no retry call made.
3. missing question (input): Questions 1, 3 -> exit 2, runner call count 0.
4. missing question (output): solver omits id 2 -> id 2 FAIL `missing_in_output`, retried alone.
5. malformed JSON: prose answer -> `malformed_output`, retried. A fenced ```json answer is accepted. Truncated `{"questions":[` is rejected.
6. QA fail: review disagree -> FAIL, retried. QA uncertain: review unsure -> UNCERTAIN.
7. second call is not proof: review agree with no independent check and no key -> UNCERTAIN.
8. retry scope: 3 questions, only id 2 fails -> the retry prompt holds only Question 2.
9. retry exhaustion: always malformed with max 2 -> attempts 2, unresolved true, exit 1. With `--max-attempts 1` there is no retry.
10. execution failures: `TimeoutExpired` gives timeout with the attempt counted. An auth error envelope gives exit 3, the attempt not counted, and a partial JSON that is valid.
11. cost cap: each call costs 0.6 with a cap of 1.0 -> the 3rd call is not made, `stopped=cost_cap`.
12. score: MC letter, ordering permutation, numeric with unit + rounding. No key and no rubric -> points null, basis none.
13. schema: `validate` reports a missing field, a bad enum and a wrong type. Every result the tests produce validates.
14. key isolation: a sentinel in the key file is absent from all captured prompts (solve, QA, retry).
15. JSON output: result.json round-trips and validates. `write_json` refuses an invalid result.
16. Markdown output: report.md has the FORMAT blocks per question (`Final answer:`, Verification `Status:`, Grading).
17. PDF output: with the DejaVu fixture path the file starts `%PDF-`, ends `%%EOF`, xref offsets are exact and `Đáp án` maps to nonzero gids. With no font, `pdf_skipped` is set and report.md exists.
18. safe_eval: `2*sqrt(3)` evaluates. `__import__('os')`, attributes and names outside the whitelist are rejected.
19. isolation argv/env: argv has `-p` and `--output-format json`, cwd is not the repo, env has no `CLAUDECODE`. `mask()` hides `sk-ant-...` in the log.

## Verification
| Item | Command -> expected | Tier |
|---|---|---|
| 2.1-2.5 unit | `python3 -I -m unittest discover -s tools/examples/tests` -> OK, tests 1-19 | $0 |
| no key leak | `exam_run.py evals/inputs/english/input-001.md --key evals/keys/english/expected-001.md --dry-run` -> prompts printed, grep of key lines empty | $0 |
| mock end-to-end | `exam_run.py examples/english/input-001.md --mock <fixture> --out work/exam-runs/mock` -> exit 0, result.json valid, report.pdf opens | $0 |
| real run (gated) | main, after user go: `--real` on the 2 English few-shot items -> valid JSON, PDF, actual PASS/FAIL counts reported as-is | paid, small |

## Decisions
- Key used only in SCORE, after DECISION. Rejected: key in QA (spec 2 "use reference answers"),
  because the key would leak through retry prompts and break the eval invariant.
- Retries are not driven by a key mismatch, which is final FAIL. Rejected: retry after a key mismatch
  (leaks the key).
- No JSON repair, just one fence/brace strip. Rejected: copying `json_repair` (not stdlib; it also guesses at truncated answers).
- 6 modules in `tools/examples/`, reusing REQ-0002's test path. Rejected: new `tools/exam/` tree, Bash runner.
- Q1-Q3 as answered by the user on 2026-10-29 (RAW-00026): DejaVu PDF / mocks only / build after REQ-0002.

## TASK split (EPIC-003)
| Order | TASK (REQ to create) | Content | Depends on |
|---|---|---|---|
| 0 | TASK-002 / REQ-0008 | this design | - |
| 1 | REQ-0002 task (EPIC-002) | layout, `check_examples.py`, `score_eval.py`, tests dir | - |
| 2 | engine core (TBD 1+2) | 2.1 parse/schema/llm/checks/run, 2.2, 2.4; tests 1-14, 18-19 | 1 |
| 3 | report (TBD 3) | 2.5 + `exam_report`; tests 15-17 | 2 (schema only) |
| 4 | runner + benchmark (TBD 4) | prompts tuned; dry-run; gated real run on 2 English few-shot items; architecture.md Flow step 3 update | 2, 3, EPIC-002 English items |
EPIC TBD "QA stage" is folded into order 2, because DECISION cannot be tested without it.

## Open questions (each with a recommended answer)
- Q4: May PASS come from a `computed` check (code evaluates the solver's own arithmetic `expr`)?
  Recommended: yes for Maths/Physics, recorded as `independent=true` with detail "arithmetic only".
  Without it, Solve mode with no key can never PASS.
- Q5: Literature with an eval key: may a separate QA call see the key's rubric to grade the essay?
  Recommended: no in the first build. Literature gets `score.basis=none` and UNCERTAIN, with
  deterministic quote checks only, because the key must not reach any prompt.
- Q6: Mode Grade/Teach. Recommended: out of scope now (VALIDATE rejects them), because the spec scores
  answers, not learners.

## Out of scope
PDF/image exam input. Mode Grade/Teach. Batch over many files (loop in a later task). Model
comparison. Accuracy claims beyond the counts from an actual run. Caching (none, so no cache key risk).
