# Phase 77 - Answer-driven cause table and held-out gain (draft for docs/design/phase-77-answer-cause-loop.md)
Task: TASK-077 (REQ-0084, RAW-00202) · Status: draft
## Goal
When the user gives official answers, one free command (no AI) explains every wrong and every flagged-but-right answer with check results, and a second shows accuracy before/after each engine change on the learn exam and a held-out exam. Done when: replay on 2025 (plans/dgnl2025) and 2026 run 3 gives the manual causes below; the board prints both tables.
## Constraints
- Key read in ONE function (`score_rows`); check functions take no key argument. Output: numbers, fixed enums, 0/1/na booleans ("agrees key"); never a letter, option text or raw message. No LLM call, no write outside stdout.
- Board without the new flags is byte-identical (golden). Stdlib only; PDF text via PyMuPDF (already the ingest dependency) else `pdftotext` (shutil.which) else `na`.
- No cached query/prompt body changes (read-only replay): no cache key impact.
## Generality
Any exam kind with result.json + exam file (+ optional calls/, PDF); normalisation is Unicode `isalnum` 3-grams (no language literal); option labels come from the exam question, not A-D; one test uses a synthetic non-DGNL English physics exam.
## Known incidents
none in docs/notes/incidents.md for this path (coordinator to confirm).
## Plan modes
solve/ingest/refine: not affected (read-only). run-stats stats/compare/trend/backfill/recheck: unchanged. board: two optional flags.
## Design
### 77.1 Question join (owner: new `pipeline/explain.py: join(result, exam, calls_dir) -> [row]`)
- Per id: exam question (stem, options, passage, group instruction, `Source pages`, `[Incomplete: ...]` marker), result record, producing calls: from `calls/index.jsonl` (tag, pages) + each `NNN-reply.txt` parsed with `claude._objects` (claude.py:133); a call "covers" id when a parsed object has that id. Producing text call = last solve/retry covering id; image call = tag image covering id. No calls/ (2026 run 3): prompt = exam text, `prompt_src=exam`, call checks `na`.
- Printed number = id + offset (`parser._OFFSET_RE`, parser.py:266, as `deps()`); key ids are printed numbers (implementer checks `len(key_letters)` only).
- Rows kept: wrong (key differs or not answered, 64.1) and flagged-right (`metrics._flagged`, metrics.py:219).
### 77.2 (a) extraction check (owner: `explain.extract_check(qblock, pdf_text, next_anchor) -> {fwd, rev, opt_prompt, opt_mode, ocr_page}`)
- norm = NFKC, casefold, keep `isalnum` chars; grams = char 3-grams. `fwd` = mean over stem + each option of |grams(piece) ∩ grams(pdf)| / |grams(piece)| (pieces < 12 chars: exact normalised substring 1/0). Catches garbled or wrong text.
- `rev` = coverage of the PDF span (start = first 24 norm chars of stem in the Source-pages stream, +1 page for continuation; end = next question's anchor or stream end) by the prompt block (passage+instruction+stem+options+figure lines). Catches truncated stem and dropped options (a prefix scores fwd 1.0, so fwd alone cannot).
- `opt_prompt` < `opt_mode` (most common option count in the exam) = option missing. `ocr_page` = a Source page whose text layer < `pdf.MIN_CHARS` -> extraction `na_ocr` (unreliable, never a verdict).
- Thresholds `EXTRACT_FWD_MIN`, `EXTRACT_REV_MIN` (start 0.90 / 0.80) set from data by V0: lowest real score minus 0.05, and above the highest synthetic-defect score; both numbers recorded in Decisions.
### 77.3 (b) context delivered (owner: `explain.context_check(row) -> {ctx_passage, ctx_deps, ctx_pages}`)
Passage/group table grams coverage in the producing text prompt >= EXTRACT_FWD_MIN; each `parser.deps()` sibling's question block in the same prompt (k/n); image call `pages` ⊇ Source pages of q ∪ of its group's first member (carrier, 76.4).
### 77.4 (c) reply path (owner: `explain.path_check(row) -> {...}`)
`src` (text, image, text+image, adjudicated), `multi_json` (max objects in a covering reply), `parse_now_ok` (`extract_json(reply, schema)` accepts it today), `attempts`, `call_failed` (finding code call_failed or `error` set), `marker` (Incomplete marker), answers per path: text round (parsed reply), image (`image answer:` finding, engine.py:183-199), second (`second answer:`, engine.py:302), adjudicated.
### 77.5 (d)(e)(f) solver signals (owner: `explain.solver_check(row)`)
(d) `quotes_n`, `quotes_in_prompt` (quote check details, folded as `_rs_recheck` cli.py:1285, found in producing prompt; image call -> na). (e) `alt_reading` = uncertainty reason or decline message names another option of this question (its label as a token, or >= 0.6 gram coverage of its text). (f) `recompute` = pass/fail/na from checks kind `computed` with independent=true; value mapped by `verifier.option_for_value`.
### 77.6 Scoring + primary cause (owner: `explain.score_rows(rows, key)`, `explain.primary(row)`)
`score_rows` adds only booleans: final/text/image/second/alt/recompute `_agrees_key`. Priority (first hit wins; upstream first, since a failed call or wrong input voids later signals):
1 infrastructure: call_failed and unresolved/declined. 2 extraction: fwd or rev below min, or option missing (reliable pages). 3 context_not_delivered: any ctx check 0. 4 reply_path: a path answer agreed with key but final differs, or marker present while 77.2 passes (false marker), or not answered after malformed. 5 key_oddity_candidate: recompute maps to the final option and final differs from key (printed "candidate for human check"). 6 image_only: src image and no text-round answer. 7 solver_reasoning: extraction evaluated, no hit above. 8 unknown: extraction `na`/`na_ocr` and nothing fired. Flagged-right rows use 1-4, 6, else `none`.
### 77.7 CLI `run-stats explain RESULT_DIR... --exam FILE --key FILE --pdf FILE [--calibrate] [--json]` (owner: cli.run_stats_main cli.py:1551 choices, new `_rs_explain`)
One exam file and PDF, several result dirs (subjects); `--exam` may be omitted when `input/exam.md` exists (as `_rs_compute` cli.py:1251). Prints TSV: printed, id, subject (`[A-Za-z0-9_-]`), outcome, primary, then every 77.2-77.6 field; footer `# n_wrong .. n_flagged_right .. <cause>=k .. multi_json_questions k`. `--calibrate`: fwd/rev quantiles of all questions + synthetic-defect scores, numbers only. Exit 0, 2 on error.
### 77.8 Held-out gain `run-stats gain --spec FILE [--json]` (owner: `metrics.gain_rows(spec)`, cli `_rs_gain`)
- Spec (git-ignored, e.g. plans/gain-spec.json): `{"exams": {NAME: {"key": PATH}}, "changes": [{"change": "TASK-076", "learn": NAME, "runs": [{"exam": NAME, "before": [DIR|run_id], "after": [...]}]}], "noise": {NAME: [[DIR...], [DIR...]]}}`; run_id resolved by `_rs_resolve` (cli.py:1231), so regset runs work.
- Row per change x exam: role learn|heldout, n (ids in both), before_k, after_k, Wilson 95 (`metrics.wilson` :223), fixed, regressed, flag `small_n` when fixed+regressed < 5, noise flips (from spec pair, else `assumed_5pct` = ceil(0.05 n)), verdict: `heldout_gain`/`heldout_loss` only if role heldout, |after-before| > noise flips and `metrics.decisive` and not `metrics.noise` (:549-568); learn rows always `learn_only`; else `no_measurable_change`.
- Reading rules (printed under the table): a learn-exam gain is not evidence; claim only heldout_gain; one run each flips ~5 percent of answers; small_n rows are anecdotes; overlapping intervals = no claim.
### 77.9 Board (owner: `_rs_board` cli.py:1489, `metrics.board_text` :752)
`--explain TSV` (repeatable) and `--gain TSV`: append `causes <cause>=k ... (wrong n, flagged-right m)` and the gain rows + reading rules. Absent: output unchanged.
### 77.10 Process rule (file: docs/guide/workflow-roles.md, new "## 10. Answer-driven learning loop"; main edits)
"When the user gives official answers: keep the list in git-ignored input/; run `run-stats explain` per saved run (free) into reports/; record cause counts and question numbers only; fix only engine causes (infrastructure, extraction, context_not_delivered, reply_path), one task each; after a fix run `run-stats gain` and claim a gain only from a heldout_gain row; send key_oddity_candidate rows to the user as a one-click check, never change the key."
## Manual causes reproduced (expected replay; data decides, never tuned)
| Q | manual | check that fires | primary |
|---|---|---|---|
| 2025 16 | solver reasoning | all checks pass | solver_reasoning |
| 2025 59 | malformed retry, image flipped | multi_json=2, text_agrees_key=1, src image | reply_path |
| 2025 60 | malformed route; solver | multi_json=2, text and image agree, both differ | solver_reasoning (reply_path if text_agrees_key=1) |
| 2025 67 | solver or key oddity | recompute=na (no computed check saved) | solver_reasoning |
| 2025 107, 117 | image = key, text kept | text_image_differ=1, image_agrees_key=1 | reply_path |
| 2025 111 | false missing_text flag | marker=1 and fwd/rev ok, src image | reply_path |
| 2026 24, 63 | solver reasoning | extraction ok, prompt_src=exam | solver_reasoning |
| 2026 38 | not analysed | extraction ok | solver_reasoning |
| 2026 65 | likely key oddity | recompute=na | solver_reasoning (key oddity needs a saved independent check) |
| 2026 112 | rate limit | call_failed, error, declined; alt_reading=1 | infrastructure |
English malformed path: footer multi_json_questions = 9 on plans/dgnl2025/out-English.
## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| no PyMuPDF and no pdftotext | extraction na | `pdf_text=na` in footer, primary unknown |
| anchor not found in PDF | rev na, fwd kept | rev `na` |
| OCR page | no extraction verdict | ocr_page=1 |
| no calls/ | prompt = exam, call checks na | prompt_src=exam |
| key ids do not match (offset) | exit 2 "key matches 0 of N ids" | error, no table |
| spec run sets differ | score intersection | n column |
## Unit tests (tests/unit/test_explain.py, tier 0, synthetic fixtures)
stem truncated -> rev < min, primary extraction; option missing -> opt_prompt < opt_mode; passage absent from prompt -> ctx_passage 0, context_not_delivered; sibling block absent -> ctx_deps; image call missing carrier page -> ctx_pages 0; quote not in prompt -> quotes_in_prompt 0; two JSON objects -> multi_json 2, and text agree -> reply_path; image-only -> image_only; marker with full text -> reply_path; call_failed -> infrastructure; recompute agrees final -> key_oddity_candidate; priority order (two causes -> earlier wins); OCR page -> na_ocr; every TSV cell matches `^(-?[0-9.]+|na|na_ocr|<enum>)$` with a key whose labels are unique letters (no leak); check functions have no `key` parameter (inspect); gain: Wilson numbers by hand, small_n, learn_only, heldout_gain needs decisive; board golden unchanged without flags; synthetic English physics exam passes.
## Verification (all tier 0, free, no paid call)
| Item | command -> expected |
|---|---|
| V0 77.2 | `run-stats explain plans/dgnl2025/out-* --exam .. --key .. --pdf .. --calibrate` -> quantiles; thresholds recorded |
| V1 77.7 | explain on plans/dgnl2025/out-* -> 7 wrong rows, causes as table above |
| V2 77.7 | explain on work/dgnl-real/run3-* with --exam each refined file -> 2026 rows as table above |
| V3 77.4 | footer multi_json_questions 9 (English 2025) |
| V4 77.8 | gain spec TASK-076: learn 2025 113 -> 111 learn_only; 2026 slice and regset no_measurable_change, small_n |
| V5 77.9 | board with/without flags; without = byte-identical to current |
| V6 AC2 | `grep -cE` of key letters per printed id in all outputs: the TSV-cell test + a manual check that no output line holds an option letter column |
| V7 | `python3 -I -m unittest discover -s tests/unit` -> OK |
## Decisions
- New module explain.py (metrics.py is ~800 lines) - rejected: inside metrics.
- Two-way gram coverage - rejected: difflib ratio (slow on pages, misses truncation one-way).
- Key oddity only from a saved independent computed check - rejected: inferring from solver confidence; Math runs hold no computed check, so 65/67 stay solver_reasoning (an inspector recompute input is out of scope).
- Gain from an explicit spec - rejected: guessing pairs from history (learn/held-out role is a human choice).
- D-coordinator-1 Scope adds 77.11 (designer defect D1): `adapters/claude.py:32-33` must treat the usage-limit message ("hit your 5-hour limit", reset time) as a rate limit/stop so a run stops instead of continuing and producing fake wrong answers (Science 112 in 2026 run 3).
- D-coordinator-2 The process rule (77.10) is written by the coordinator into docs/guide/workflow-roles.md section 10 after the code is verified.
- D-coordinator-3 The tool never prints key letters; key oddity candidates need a recorded independent recomputation, otherwise the cause is solver_reasoning (designer note).
## Out of scope
New paid runs or a noise-baseline run; recompute inputs from humans; changing merge rules.
## Defects
- D1 medium src/exam_engine/adapters/claude.py:32-33: "You've hit your 5-hour limit" is not rate_limit (no "5-hour"/"hit your" word) -> error cls "other" (work/dgnl-real/run3-Science/result.json:1112), so the run went on instead of stopping (engine.py:19 BLOCKING).
- D2 low work/TASK-037/evidence/dgnl-score.txt:34: Science 112 "not a wrong answer": it is solver_declined with an answer and an alternative reading (run3-Science/result.json:1090-1095) whose retry failed on the limit.
- D3 info: no `computed` check in plans/dgnl2025/out-Math or run3-Math: (f)/(g) cannot fire on Math 65/67.
- D4 low docs/req/items/REQ-0084.md:28: stray empty "- [ ] AC1:" line.
- D5 info: run3-* have no calls/ or input/: 2026 context/prompt checks are na.
Nova
