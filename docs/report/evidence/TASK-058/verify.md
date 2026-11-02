PROGRESS: COMPLETE
SKILLS: verify-phase, verify, crosscheck, token-efficiency
Scope: REQ-0062 AC1-AC5, docs/design/phase-58-plan-report-split.md. Tier 0/1 only (mock/local); no paid run. Verdicts are claim verdicts; state VERIFIED stays with main.

## Per-AC verdicts
- AC1 layout + git-ignored + collision-safe: VERIFIED (code/tests). planrun.py:26-38 claim_run_dir = makedirs(exist_ok=False) loop, UTC stamp, -N suffix; .gitignore:2 `reports/*`, :14 `plans/`; tests/unit/test_planrun.py:78-83 `git status --porcelain` == "" after solve in a git repo seeded with the real .gitignore; test_plan_qa (3 solves in a frozen second -> 3 distinct ids, test.md). Doc: only one line in docs/guide/toolkit-reference.md plus CLAUDE.md §11; the full layout lives in the design doc (thin, see G7). Tick box requires "documented": accept design doc + toolkit-reference line.
- AC2 solve writes plan run with raw replies; reports under reports/ from plan: VERIFIED (unit, mock). planrun.py:93-113 PlanWriter.record writes calls/NNN-{prompt,reply}.txt + index.jsonl (sha256, bytes, tag); engine.py Runner sink runs after each call (code.md round 1); crash test keeps call 001 and plan.json status failed (test_plan_qa, mutation M2 killed); cli.py:154 default report to reports/<exam>/<run>/sheet; --out stays flat. Real raw replies from a real model: UNVERIFIED (no paid run).
- AC3 report from plan, zero AI, deterministic: VERIFIED. report_build.py imports (lines 6-10) = hashlib/json/os + metrics, parser, planrun, reporter, router; none of these imports adapters/engine/claude/socket (grep: only reporter imports subprocess, for git_info). Guard test test_report_build.py:24 FORBIDDEN list + AST check (:78-89) + claude/subprocess/socket patched to raise (:92-95); determinism test (8 tests, code.md); mutation M1 (import adapters) killed. Caveat: AST guard checks direct imports only, not transitive; reporter's subprocess is git only.
- AC4 history with plans; run-stats accepts plan runs; compare/trend unchanged: VERIFIED. cli DEFAULT_HISTORY plans/run-history.jsonl, legacy reports/ and results/ read-only (code.md); evidence work/TASK-058/evidence/qa7-import-stats.txt (rc 0): stats lines identical old vs imported, compare unchanged:1.
- AC5 plan-import + old result dirs + docs: VERIFIED with limits. planrun.py:196-253 import_dir; idempotent on (imported_from, result sha); evidence plan-import-real.txt (rc 0, header) real work/dgnl-real import, second import skipped, report built; qa7 shows result.json byte-identical, replies "not captured". Docs pointer: CLAUDE.md:20 (§11) and toolkit-reference.md:12. Limits documented in code.md only (see G3,G4).
- Old form `report RESULT.json --out` still works: VERIFIED. cli.py:279-281 dir first arg -> _report_plan, file arg -> old path; test_report_build "old form" test (code.md round 2).

## Specific checks
- plans/ and reports/ never tracked: VERIFIED (test_planrun.py:78-83, .gitignore:2,14).
- No AI/network in report engine: VERIFIED (above).
- Raw calls captured per call before run end: VERIFIED by unit (sink after each call; crash test; plan.json exists before first call, test_plan_qa). Capture failure = one WARN, run continues (planrun.py:5-6 doc).
- Masking + sha of unmasked: VERIFIED. planrun.py:101-108: reply written via claude.mask, reply_sha256 = _sha(text) of unmasked; prompts stored UNMASKED; M3 killed. Note sha of an unmasked secret-bearing reply is an offline-guessable hash (low).
- Plan-import limits (trace only inside run dir; ingest cache only if exactly one hash dir or --ingest-cache): ACCEPTABLE. planrun.py:181-193 matches code.md note; real ingest cache had PNGs only. Documented in code.md and cli help (cli.py:266-267), not in docs/guide.
- History placement: VERIFIED as above.
- Suite: suite-final.txt Ran 985, failures=3 errors=1 vs baseline-failures.txt Ran 847, same 3/1 (expected_failures 2, skipped 35 equal). Same failure counts; names listed in test.md (lxml docx, check_examples x2, cwd_independence). Did not diff names myself: head-failures.txt vs baseline only by count. UNVERIFIED that the 4 are identical tests (ask main for `diff` of the FAIL/ERROR lines).

## Security pass (git diff 083d0e4..HEAD, read of planrun.py, cli.py:232-276, report_build.py)
- exam-id: planrun.py:22-23 basename+splitext, so no traversal from the exam path. `--exam-id` (cli.py:265) and import `exam_id` are used raw in os.path.join(root, exam_id) -> `--exam-id ../x` escapes plans/. Local CLI arg by the operator: LOW.
- report-id / --id (cli.py:239,246): joined raw -> `../..` escapes reports/. LOW, same reason (operator-supplied). plan-run-id/exam_id read from plan.json meta (cli.py:244-245) and joined into the report path: a hostile imported plan.json could steer the report dir (`plan_run_id: "../../x"`). LOW-MEDIUM since plan dirs are copied from untrusted clones.
- --out: written as given, same as before (not new).
- Import symlinks: shutil.copyfile follows file symlinks (planrun.py:216,219,228,234,242): a *.trace.json or cache file that is a symlink to a secret is copied into the plan (local, git-ignored). os.walk does not follow dir symlinks. LOW.
- Import reads `result.json` field exam.path (planrun.py:208-211): untrusted result dir can point at any readable local file, which is then copied to input/exam.md and (if report-built) rendered into reports. Information-disclosure to a local ignored dir, LOW-MEDIUM.
- subprocess: planrun/report_build/cli changes add none beyond reporter.git_info (git, fixed argv); no shell.
- Secrets in calls/: replies masked via claude.mask (token patterns only); prompts unmasked (contain exam text only; user-controlled). Config stores key path + sha256, not the key (planrun.py:67). OK.

## Gaps (honest)
- G1 no paid run: raw capture against a real `claude` call (stdout shape, long replies, retry/QA tags) is mock-verified only.
- G2 old runs (work/dgnl-real etc.) have no raw solve replies: imported calls are `captured:false`, "not captured"; ingest caches had PNGs only. Raw AI output for those cannot be recovered (answers RAW-00176 only for new runs).
- G3 refine traces (work/dgnl-real/v3/*.trace.json) are not auto-imported; needs copy into run dir or --ingest-cache (no --trace flag). Decision for main.
- G4 imported plan from real dgnl-real had no exam file -> no key metrics in the report.
- G5 REQ-0059 (image check) / REQ-0058 interplay not exercised: ingest traces are copied as opaque files, no report view reads them; no test of a later image-check consuming plans/<e>/<run>/ingest.
- G6 parity tested on the english fixture only; real work/dgnl-real import not re-run by tester (test.md Gaps).
- G7 documentation of AC1 layout is one line in toolkit-reference.md:12; no standalone layout doc.

## Defects
- D-V1 LOW cli.py:239,246,265 / planrun.py:28: --report-id, --exam-id (and meta exam_id/plan_run_id, cli.py:244-245) joined into paths unsanitized -> `..` escapes plans/ and reports/. Fix: reject values with os.sep or `..` (one validate function).
- D-V2 LOW planrun.py:208-211,216-242: import follows file symlinks and result.json exam.path from an untrusted dir. Fix: skip symlinks (os.path.islink) and require the exam path to be given via --exam, or inside the run dir.
- D-V3 INFO test_report_build.py:78-89: AST guard is direct-import only; add a runtime check (sys.modules has no exam_engine.adapters after build) for transitive imports.

## NEXT
Main: run `diff` of FAIL/ERROR names between head-failures.txt and baseline-failures.txt via save-evidence; decide D-V1/D-V2 (fix now or log) and G3; then tick AC1-AC5 and advance. Real-call capture check waits for the next approved paid run.
