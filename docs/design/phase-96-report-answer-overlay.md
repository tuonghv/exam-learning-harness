PROGRESS: COMPLETE
SKILLS: design, token-efficiency

# Phase 96 - report overlay 
Task: TASK-096 · REQ-0103 AC1-AC5 · Status: draft

## Goal
`report-pack` / `exam publish` take `--overlay PLAN_DIR:PRINTED[,PRINTED...]` + `--overlay-reason TEXT`: the listed printed numbers take answer, solution, status, doubt and checks from the overlay plan run. The change exists only in memory: no result.json is written. run.json `overlays` records it, and each overlaid block has one source line. DHQG 2024: t81 base + t82 printed 64-67 -> 115 answered / 5 declined of 120.

## Facts found (read-only, plans/dhqg2024)
- Offsets come from the "printed exam number of question N is N + K" line in each `input/exam.md:14`: Vietnamese 0 (no line), English 20, Math 40, Science 70. They confirm the brief's offsets.
- Printed 64-67 = Math (`t81/runs/20261107-005940-math`) ids 24-27. Assembly confirms the `printed` mapping (`t81/e-Math.md.assembly.json:241-272`, pages [8]).
- t82 run `20261107-014525`: plan.json exam_id `e-64-67`, subject Math, offset 63 (`input/exam.md:14`), ids 1-4 = printed 64-67 (`t82/e-64-67.md.assembly.json`), pages [8]. Answers 1..4 = D, A, D, B, all UNCERTAIN/no_independent_check, unresolved false, cost 0.064319.
- Base t81 Math ids 24-27: answer null, `solver_declined`, unresolved true, evidence_kind none (`result.json:1267-1407`). t81 `answer: null` total = 9 (Math 5, En 2, Vi 1, Sci 1). After the overlay: 5 declined, 115 answered.
- Text: instruction, stem and options A-D are visually identical (t81 `input/exam.md:416-502` vs t82 `:16-124`). Only the passage table differs: t81 has a placeholder description, t82 has 5 rows of values (the fix). So the identity hash must cover stem+options only. Bytes are not hashed yet (no Bash); the validator built here confirms it on the first build.
- Both plan dirs resolve to exam `dhqg2024` through plans/MIGRATION.json (`runlayout.exam_line_of_plan_dir`). Lines are t81 and t82.
- Current main run: `reports/dhqg2024/main/run-20261108-072402` (from t81 pack `run-20261108-061132`). It records no key, so no score files are made (score-summary is n/a).

## Plan modes
- Solve/plan runs: not affected; the change is report-only, $0.
- Packs without `--overlay`: output stays byte-identical. The golden tests are the existing report-pack/publish tests (`test_publish.py`, `test_report_kinds.py`, `test_report_wording.py`).
- No cached query or prompt changes, so no cache key is touched.

## Design
### 96.1 Overlay resolve + validate (new `src/exam_engine/pipeline/overlay.py`)
- `parse(spec) -> (plan_dir, [int])`. `resolve(specs, plan_dirs, reason) -> [entry]`. Every check runs BEFORE any file is written. Each failure raises a ValueError naming the printed number. Refuse when:
  1. the overlay dir has no result.json or input/exam.md, or is one of the base plan_dirs;
  2. its exam (`exam_line_of_plan_dir[0]`) differs from the base exam;
  3. its `result.exam.subject` does not match exactly one base part;
  4. a printed number repeats (in one spec or across specs);
  5. `printed - offset` (`explain.offset` of each parsed exam) is missing in the base or overlay result or parsed exam (unknown id);
  6. `text_sha256` differs. It is sha256 of json `{stem, options}`, whitespace collapsed via `reporter._one_line`, sort_keys. Passage and instruction are excluded on purpose;
  7. both questions have `pages` and the page sets are disjoint;
  8. the base question is answered and not `unresolved` (only declined/unresolved base questions may be replaced);
  9. the overlay question has no letter answer.
- `--overlay-reason` is required with `--overlay`. It is untrusted text, printed through `_one_line`.
- Entry shape. It reuses the plan_runs keys, so run-list sees it (96.4):
  `{exam_id, line, plan_run_id, dir, result_sha256, subject, base_plan_run_id, reason, cost_usd, questions:[{printed, base_id, id, text_sha256}]}`.

### 96.2 Apply at render time (overlay.apply; report_build.build gains `overlay=None`; report_pack.build_pack gains `overlays=None`)
- `apply(result, exam, entry, ov_result, ov_exam) -> (result', exam')` works on deep copies. For each question in the entry:
  - the base question is replaced by the overlay question with `id` = base_id and `overlay` = {plan_run_id, line, reason};
  - in the parsed exam, the base question is replaced by the overlay exam question (its passage holds the fixed table) with id = base_id.
- `summary` pass/fail/uncertain/unresolved is recounted from the merged questions; points and max_points are kept.
- report_build.build (`report_build.py:46-70`) applies it after `planrun.load`, then reuses metrics/write_reports unchanged. result-data json gets `overlays: [entry]` for that subject. result_sha256 stays the base hash.
- build_pack (`report_pack.py:113`): `resolve` runs first, then each entry goes to its subject's plan. `extra["overlays"] = entries` goes to run.json (`runlayout.write_report_manifest` already merges extra).
- reporter `_question_block` (`reporter.py:211`): when `q.get("overlay")`, add one bullet straight after the answer line, using a new label `LABELS[lang]["overlay"]`:
  - vi: `- Nguồn đáp án: lần chạy plan <id> của line <line> (<reason>)`
  - en: `- Answer source: plan run <id> of line <line> (<reason>)`
  - Blocks without `overlay` are unchanged.

### 96.3 What each kind shows (with an overlay)
| Kind | Shows |
| --- | --- |
| solution-report (Math, all), answer-sheet Math, answer-table tsv, metrics.json Math | merged answers |
| Math header and combined Totals | recounted |
| Header Run line and metrics cost | base run only; overlay cost lives in run.json `overlays[].cost_usd` |
| tsv | columns unchanged; only 4 letter/status/doubt cells differ |
| score-vs-key / score-summary | keyed only (none for dhqg2024) |
- `tools/check_report_pack.py:99-162` reads run.json `overlays`. For each entry it checks:
  - the sha256 of `dir`/result.json equals the recorded `result_sha256` (row `overlay result_sha256 mismatches` 0);
  - the "### Question text" section of both input/exam.md files is equal after whitespace collapse (own regex; row `overlay text differs` 0);
  - `want[(subject, base_id)]` is replaced by the overlay letter before the answer-table and key recount;
  - `overlay source lines <subject>` = len(questions), and the same count holds in the combined report (regex on the label start, vi|en).
- Plan args stay the base plans only.

### 96.4 Publish + run-list (cli.py)
- `report_pack_main` (`cli.py:459`) and `publish_main` (`cli.py:509`) get `--overlay` (repeatable) and `--overlay-reason`.
- publish: when no `--overlay` is given, it inherits the source pack's run.json `overlays`, the same way it inherits the key (`cli.py:536`), and prints `overlay inherited: <plan run> printed 64-67`. An explicit `--overlay` replaces the inherited one.
- `_publish_selection` keeps using `plan_runs` only, so the t82 run does not break the "all in line" test (`cli.py:499`).
- publish prints `main: run-<prev_report_run> -> run-<new>` (the old -> new announcement, AC4).
- `_rl_plan_keys` (`cli.py:1453`) iterates `plan_runs + overlays`. Then `linked()` and `pub_links` mark t82/20261107-014525 as `published`, with no change in `linked`.

### 96.5 Dev-first flow (main runs it)
1. `exam report-pack <4 t81 dirs> --exam dhqg2024 --no-pdf? --overlay plans/dhqg2024/t82/runs/20261107-014525:64,65,66,67 --overlay-reason "chạy lại sau khi sửa bảng"`. The line mirrors the first plan, so the output goes to `reports/dhqg2024/t81/run-<id>`.
2. QA (96.6).
3. `exam publish dhqg2024 --from t81`. It inherits the overlay and makes a new main run; `run-20261108-072402` stays.

## Failure modes
| Failure | System response | Operator sees |
| --- | --- | --- |
| text differs / unknown printed / answered base / other exam | ValueError before any write; publish rmtree's the half run (`cli.py:549`) | `ERROR: overlay printed 64: ...`, exit 2 |
| overlay plan edited after the pack | checker sha row FAIL | `overlay result_sha256 mismatches 1 FAIL` |
| overlay id vs base id confusion | block heading uses base_id; checker counts `### ` heads per subject | count rows FAIL |
| reason missing | argparse error | exit 2 |

## Unit tests (tmp trees, a synthetic non-DGNL exam: subject "Physics" offset 10, overlay offset 12; new `tests/unit/test_overlay.py`)
- T1: overlay applied; the overlaid rows of answer-table/answer-sheet carry the overlay letters; each overlaid block has one source line (vi and en); every other `### ` block is byte-equal to a no-overlay pack.
- T2: refusal (each its own case) on an option text mismatch, unknown printed, answered base, other exam, subject not in base, duplicate printed, missing reason. In each, the out dir has no run.json.
- T3: base plan files have the same sha256 before and after.
- T4: run.json `overlays` shape plus result-data `overlays`; recounted Totals line.
- T5: `python3 -I tools/check_report_pack.py` passes on the overlay pack and fails after the overlay result is tampered.
- T6: publish inherits overlays; `run-list` shows the overlay plan run `published`; earlier main run kept.
- Golden: a no-overlay pack is byte-identical. The existing tests stay green unchanged.

## Verification (main, $0, real tree)
| Item | Command -> expected |
| --- | --- |
| 96.1/96.2 | `sha256sum` over `find plans/dhqg2024 -type f` before = after |
| 96.2 | dev pack: Math ids 24-27 answers D, A, D, B; 4 source lines in Math and in all; 0 `\bnone\b` in the solution-report md |
| 96.2 | split the combined report at `^### ` and diff against `reports/dhqg2024/t81/run-20261108-061132` -> 116 blocks byte-equal, 4 differ |
| 96.3 | answer-table: 120 rows, 115 letters, 5 `-`; `check_report_pack.py <pack> <4 t81 dirs>` all ok |
| 96.4 | publish -> new main run with `published_from` t81 and `overlays[0].plan_run_id` 20261107-014525; `run-list dhqg2024` t82 row = published; old main run present |

## Decisions (main may settle; no user decision needed)
1. Identity = stem+options hash; the passage is excluded (it is what the fix changed). Rejected: the full block hash, which would always refuse here.
2. Base must be declined/unresolved. Rejected: replacing answered questions (add a flag later if needed).
3. Overlaid block shows the overlay passage (the fixed table). Rejected: the base placeholder, which contradicts the answer.
4. publish inherits overlays like the key (best). Rejected: requiring `--overlay` again on publish.

## Out of scope
Fixing the section label (D1); score files (no key).

## Defects
- D1 low: the Math questions sit under `## Section: 1.2. TIẾNG ANH`. Location: `plans/dhqg2024/t81/runs/20261107-005940-math/input/exam.md:16` and `plans/dhqg2024/t82/runs/20261107-014525/input/exam.md:16`. Evidence: both files show this section label for Math-subject questions. Extraction carry-over; it does not affect the hash.
- D2 info: plan.json `exit_code` is 1 with `status: done` in both t81 Math and t82 (`plan.json:11`). t82 `plan_run_id` is `"run"` (`t82/.../plan.json:20`). The manifest uses the basename, so no impact.

Nova
