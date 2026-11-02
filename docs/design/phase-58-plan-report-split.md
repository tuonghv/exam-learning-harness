# Phase 58 - Plan/report split
# Phase 58 - plan/report split (draft for docs/design/phase-58-plan-report-split.md)
REQ-0062 (RAW-00175) · Supersedes: phase-57 Revision 57.8 (default out, history path) · Status: draft
## Goal
`solve` writes a PLAN run plans/<exam-id>/<plan-run-id>/ (config, input, every raw prompt/reply, result.json);
`report PLAN_RUN` rebuilds reports/<exam-id>/<plan-run-id>/<report-id>/ with zero AI calls, deterministically.
Proof: rebuild twice with the adapter and network forbidden gives byte-identical trees (58.6).
## Constraints
- plans/ and reports/ stay git-ignored (.gitignore:2 `reports/*`, :14 `plans/`). Neither is ever evidence.
- The key file is never copied into a plan (eval keys stay out of eval inputs); only its path + sha256.
- test_guards.py:31: only reporter + adapter start processes. The new builder starts none itself.
- Old callers stay as they are: `benchmark` (benchmark.py:65 engine.run), `report RESULT.json --out DIR`
  (test_scripts_exam.py:63, test_exam_report.py:604), `run-stats DIR`, test_default_out.py:63.
## Known incidents
none found (not grepped beyond the files below).
## Plan modes
Solve gains plan-run capture; report/review/run-stats read plan runs. Ingest, refine and cross-solve unchanged. Old result dirs are read through plan-import; `--out` stays honoured.

## 1. Current flow and gaps
- solve_main cli.py:30 -> engine.run engine.py:128 -> Runner.call engine.py:37 (the only solve-path LLM call;
  callers solver.py:141, verifier.py:224) -> result.json + run.log (engine.py:177-181) ->
  metrics.compute(exam=exam) :183 -> reporter.write_reports(out_dir) :186 (report.md, answers.md, html/pdf).
- History: cli.py:150 `_append_history` (only --real/--history), DEFAULT_HISTORY reports/ cli.py:24.
- `report` cli.py:220 reads RESULT.json + the run.log next to it; metrics computed WITHOUT the exam.
- Lost today: G1 every raw prompt and reply (run.log keeps only bytes/cost/dur/cls, engine.py:45); G2 retry
  and QA prompts; G3 the exam text (result has only exam.path; sha only in the history line); G4 config
  (lang, channel, key sha, pdf not in result.run); git commit only in history, only for --real;
  G5 wall_s (printed + history only); G6 a crash other than Stop (exception, Ctrl-C) writes nothing, so
  all paid replies are lost; G7 cross-solve/ingest-refine traces keep ok/cls/cost only (refine.py:96) - out of scope here.
## 2. Layout
```
plans/run-history.jsonl                     # REQ-0060 history (AC4)
plans/<exam-id>/<plan-run-id>/
  plan.json      meta (below)
  config.json    cfg as used; "key": {"path","sha256"} | null (never the key text)
  input/exam.md  byte copy of the exam file
  calls/index.jsonl          one line per call, appended + flushed after every call
  calls/NNN-prompt.txt, calls/NNN-reply.txt   NNN = 001.. (zero-padded call number)
  result.json, run.log       same as today (compat: run-stats, metrics.load_log, backfill)
reports/<exam-id>/<plan-run-id>/<report-id>/
  report.md, answers.md, [report.html, report.pdf], metrics.json, report.json
```
- exam-id = exam file basename without extension (as _default_out cli.py:141). plan-run-id = UTC
  `%Y%m%dT%H%M%SZ`, `-N` on collision; claimed with os.makedirs(exist_ok=False) in a loop (race-safe).
- plan.json: {schema_version:1, exam_id, plan_run_id, source:"solve"|"import", status:"running"|"done"|
  "stopped"|"failed", exit_code, started_utc, finished_utc, wall_s, git:reporter.git_info(root),
  prompt:prompts.prompt_info(), model, llm, config_sha256 (sha256 of canonical config.json, sort_keys),
  exam:{path, sha256}, calls, cost_usd, calls_captured:bool, imported_from:null|path}.
  Written with status "running" before call 1, rewritten at the end (G6: a crash leaves running + calls/).
- index.jsonl line: {n, tag:"solve"|"retry"|"qa", ok, cls, reason (claude.mask, <=200), duration_s,
  cost_usd, prompt_bytes, reply_bytes, prompt_sha256, reply_sha256}. reply.txt = Call.text as received
  (the parsed JSON source), passed through claude.mask (token pattern only); sha256 is of the unmasked text.
- Size: replies are KB; no cap in v1. Images (cross-solve) not captured.
## 3. Report engine contract
### 58.1 Raw call capture (owner: engine.py Runner, new pipeline/planrun.py)
`Runner(cfg, llm, log, sink=None)`; `call(prompt, tag=None)` calls `sink(n, tag, prompt, call)` after each call.
solver.py:141 passes tag "solve"/"retry", verifier.py:224 "qa". sink=None keeps today's behaviour (benchmark).
planrun.py: `claim_run_dir(root, exam_id) -> path`, `PlanWriter(dir, exam_path, cfg)` with `.start()`,
`.record(n, tag, prompt, call)`, `.finish(result, code, wall_s)`; `load(plan_dir) -> dict(plan, result, log, exam_text)`.
### 58.2 Plan written by solve (owner: cli.solve_main, engine.run)
`engine.run(exam_path, out_dir, cfg, llm, sink=None, reports=True)`; solve passes the PlanWriter sink and
reports=False, wraps run in try/finally so finish() runs on exceptions (status failed). Stop -> "stopped".
### 58.3 Report builder (owner: new pipeline/report_build.py)
`build(plan_dir, out_dir, *, view="sheet", pdf=False, renderer=None, runner=None, engine_git=None) -> info`
Input = only planrun.load(plan_dir). Parses input/exam.md (if present) and calls
metrics.compute(result, log, exam=exam), reporter.write_reports(..., metrics=m), writes metrics.json
(sort_keys) and report.json {plan_dir_rel, plan_run_id, result_sha256, view, engine_git}. No timestamps
in any file. Imports allowed: planrun, parser, metrics, reporter, settings. Starts a process only through
reporter.md_to_pdf when pdf=True (local renderer, no AI). Review pack stays separate (stateful,
review-apply writes back); it already takes `--result plans/.../result.json`.
### 58.4 CLI `report` (owner: cli.report_main)
`report PLAN_RUN [--view sheet|learn] [--id RID] [--no-pdf] [--out DIR]`: PLAN_RUN = dir with plan.json
or result.json. Default out reports/<exam-id>/<plan-run-id>/<RID>; RID default `<view>`; same RID =
overwrite (identical by 58.6). Old form `report RESULT.json --out DIR` unchanged (first arg is a file).
### 58.5 solve output (owner: cli.solve_main, _default_out)
No --out: plan at plans/<exam>/<run>/, then report_build into reports/<exam>/<run>/sheet/; prints both
paths. `--out DIR`: plan files in DIR and the report flat in DIR (old layout, benchmark/tests unchanged).
### 58.6 Determinism + AI-forbidden (owner: tests)
### 58.7 `plan-import DIR [--exam EXAM.md] [--exam-id ID]` (owner: cli, planrun.import_dir)
Copies result.json, run.log (if any) into a new plan run; plan.json source "import", calls_captured
false, imported_from DIR; input/exam.md from --exam or result.exam.path when readable (sha recorded),
else absent. Same (imported_from, result sha) already imported -> "skipped", exit 0.
Works for results/*, work/dgnl-real/run*/ (result.json + run.log + report.md layout).
### 58.8 History (owner: cli.DEFAULT_HISTORY, LEGACY_HISTORY, _append_history)
DEFAULT_HISTORY = plans/run-history.jsonl; LEGACY_HISTORY becomes a tuple (reports/..., results/...), both
read-only in `_rs_lines` cli.py:982. Line gains "plan_dir"; run_id format unchanged. compare/trend untouched.
`run-stats stats|compare PLAN_RUN` already works (result.json at root, cli.py:995); add: use
input/exam.md when --exam is absent.
### 58.9 Docs: toolkit-reference.md:12, CLAUDE.md pointer (main), cli.py:47 help text.
## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| crash mid-run | finish() in finally: status failed, calls/ kept | ERROR + plan path |
| report on a plan with status running/failed | build from result.json if present, else exit 2 | "plan incomplete: no result.json" |
| capture write fails (disk) | WARN once, run continues (capture never fails a paid run) | WARN: capture off |
| plan-import of a dir without result.json | exit 2 | "not a result dir" |
| two solves same second | -N suffix via makedirs(exist_ok=False) | distinct ids |
## Unit tests (tests first; mock LLM only, no paid run)
- test_planrun.py: mock solve with 1 retry + QA -> calls/001..00N, index.jsonl tags solve/qa/retry,
  N == result.run.calls, sha256 match, config.json has no key text, input/exam.md == source bytes.
- crash: llm raising RuntimeError at call 2 -> plan.json status failed, 001 files present.
- test_report_build.py determinism: build(pdf=False) twice into 2 temp dirs -> identical file list + bytes.
- AI-forbidden: patch adapters.claude.run_claude/_run, subprocess.run/Popen, socket.socket to raise;
  build(pdf=False) succeeds. Static: AST of report_build.py imports none of engine, adapters, solver,
  verifier, socket, urllib, http, subprocess (extend test_guards.py).
- parity: report.md from build == report.md from solve --mock (pdf off), incl. ## Metrics.
- CLI: solve without --out -> plans/<e>/<id>/ + reports/<e>/<id>/sheet/; git status --porcelain empty
  (extend test_default_out.py); `report RESULT.json --out` old form still passes.
- plan-import of a copy of a work/dgnl-real/run1 fixture shape -> plan.json source import; second import skipped.
- history: default path plans/run-history.jsonl; legacy lines from both old paths read by trend.
## Verification (cost tier 0: mock/local only)
| Item | command -> expected |
|---|---|
| 58.1-58.2 | `python3 -I scripts/exam.py solve examples/<fixture>.md --mock M.json` -> plans/<e>/<id>/calls/ has 2*N files |
| 58.3-58.4, 58.6 | `report plans/<e>/<id> --no-pdf --id a` then `--id b`; `diff -r` a b -> empty |
| 58.5 | solve without --out; `git status --porcelain` -> empty |
| 58.7 | `plan-import work/dgnl-real/run1` -> plans/<exam>/<id>/plan.json source import |
| 58.8 | `run-stats trend` -> includes legacy lines; `run-stats stats plans/<e>/<id>` -> metrics block |
| unit | `python3 -I -m unittest discover -s tests/unit` -> OK |
## Decisions (recommended; user/main to confirm)
- D1 plans+reports split (chosen) vs one dir per run (today, 57.8): one dir mixes cost-bearing raw data
  with cheap rebuildable output, so a report change rewrites the plan dir; split lets many reports per plan.
- D2 per-call text files + index.jsonl (chosen, AC1 names calls/NNN-{prompt,reply}.txt) vs one calls.jsonl:
  files are greppable/diffable and need no escaping; index.jsonl keeps the cheap meta in one file.
  JSONL-only would be one file but unreadable prompts (escaped newlines).
- D3 builder in a new module, not in engine: lets an AST guard prove no AI import. Reject a
  subprocess ban on PDF: PDF needs a local renderer; the AI-forbidden test runs pdf=False, PDF keeps its fake-runner tests.
- D4 RID default `<view>` (overwrite) vs timestamp: determinism makes overwrite safe; `--id` keeps versions.
- D5 keep `--out DIR` flat (plan + report in DIR) for compat; only the default changes.
- Smallest first: 58.1+58.2 (capture) alone fixes G1-G6; 58.3-58.5 next; 58.7-58.8 last.
## Needs main / user
- Q1 `_evidence.py scan/publish` (57.4) should refuse paths under plans/ and reports/ (main-owned .claude/scripts).
- Q2 masking raw replies with claude.mask (token pattern) vs storing fully raw: recommend mask + unmasked sha.
## Out of scope
cross-solve/ingest-refine raw capture (G7); copying ingest provenance (phase 43) into input/; rescoring in report step.
## Gaps
- report.md gets "PDF skipped: <note>" appended (reporter.py:367) depending on the machine: report bytes differ
  across hosts when pdf on; determinism is defined for pdf=False only.
- `report` today computes metrics without the exam (cli.py:241) so its report.md differs from solve's (:183).
## Defects
- D-1 low, cli.py:47: `--history` help says default results/run-history.jsonl; code uses reports/ (cli.py:24).
- D-2 low, cli.py:139-147 `_default_out`: exists-check then create later; two runs in the same second can share a dir.
- D-3 medium, cli.py:241 vs engine.py:183: rebuilt report lacks exam-based metric slices (not identical to solve report).
- D-4 medium, engine.py:144-181: results/log written only at the end; an uncaught exception loses all paid replies (G6).

Nova

## Decisions (coordinator)
- Q1 yes: _evidence.py scan/publish refuse any path under plans/ or reports/ (plans hold exam text and answers).
- Q2 accepted: mask secrets in raw replies with the existing claude.mask token pattern, keep sha256 of the unmasked reply.
- Order: TASK-058 starts after TASK-057 is DONE; 58.1+58.2 (raw call capture) first, it also fixes D-4 (paid replies lost on crash).

## Existing raw AI output found (RAW-00176, coordinator inspection)
Raw AI output exists today only for INGEST/REFINE, not for solve: `<out>.trace.json` beside each refine output (e.g. work/dgnl-real/v3/5-12.json.trace.json: list of {ok, cls, cost_usd, text(raw reply), reason} per call) and the reply cache `work/dgnl-real/work/ingest/<hash>/` (boundary/page entries, REPLY CACHE in ingest/replycache.py). Solve runs (run*/) keep only result.json, report.md, run.log: raw solve replies were never stored. 58.7 `plan-import` must also pick up `*.trace.json` and the ingest cache dir of the same exam into `plans/<exam>/<run>/ingest/` as raw AI output, so a plan holds both ingest and solve raw output.
