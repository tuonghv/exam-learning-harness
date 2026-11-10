# Phase 98 - dgnl2024 key score
# Phase 98 - dgnl2024 key score (draft for docs/design/phase-98-dgnl2024-key-score.md)
Task: TASK-098 · REQ-0105 (AC1-AC4) · Status: draft

## Goal
Official key input/dgnl/De-thi-mau-DHQG-HCM-2024.answer.txt scores the engine on dhqg2024: key problems are
reported (Câu 65 "I" flagged, never guessed), score-summary shows accuracy, per-subject, per-question result,
declined, doubt calibration and mismatches with the engine's answer + reasoning; first on existing runs ($0),
then on a paid re-solve (~$2, user-approved Q1).

## Constraints
- Key only scores: never copied into, or passed to, `solve` / exam inputs (e-*.md unchanged, sha-checked).
- `explain.load_key(path) -> {printed: letter}` keeps signature + output (callers: report_pack.py:128,
  metrics.py:839, cli.py:1938, test_explain.py:247).
- No-key packs byte-identical (score files only exist with `--key`).
- Generality: parser and report are exam-agnostic (any "N. X" list, any subjects); no DGNL literal in code;
  one test uses a synthetic 3-question non-DGNL key.

## Known incidents
none checked (main: grep docs/notes/incidents.md for "key").

## Design
### 98.1 Key parse report (owner: src/exam_engine/pipeline/explain.py:77)
- New `parse_key(path) -> (key: dict, issues: list)`; `load_key` = `parse_key(path)[0]` (unchanged result).
- Same tokenizer (l.80). Issue rows `{"printed": str, "kind", "token"}`:
  - `bad_letter`: number followed by a single-letter token outside A-D (Câu 65 "I"). Not added to key.
  - `duplicate`: number seen again with a different letter (first kept, as today's setdefault).
  - `missing`: n in 1..max(key ∪ bad) with neither a letter nor an issue.
- Tolerated already (assert in tests): "34. D", "Câu 105.B ", tabs.
- Expected on the real file: 119 letters + 1 issue `65 bad_letter I`; 120 entries total (AC1).

### 98.2 Score rows know key issues (owner: report_pack.py `_score_rows` l.45, build_pack l.128)
- build_pack calls `parse_key`; issues printed to stderr as `key issue: <printed> <kind> <token>` and stored
  in score-summary.json `key_issues` and run.json meta `key_issues` (l.180 block).
- `_score_rows(rows, key, issues=())`: printed with an issue -> result `keybad` (key column `?I`), not `nokey`.
- Rows gain `answer_text` (engine answer value) and `why` (reuse review.py:110 excerpt logic: first 3
  solution steps else explanation, one line, cut to ~300 chars); `why` goes to json/md only, not the tsv
  (tsv header l.160 unchanged).

### 98.3 Richer score-summary (owner: report_pack.py `_summary` l.57, `_summary_md` l.76)
- Accuracy = correct / scorable, scorable = rows with result in {correct, WRONG, declined}; `nokey`/`keybad`
  excluded and counted separately. Per-subject table adds `Scorable`, `Accuracy %`; total row same.
- `## Per question` table: printed, subject, key, ours, result, doubt, status (all rows, compact).
- `## Calibration` table: rows = doubt level (sorted), cols n / correct / WRONG / declined / accuracy %;
  json `calibration` (keep `doubt_vs_outcome` for compat).
- `## Mismatches (n)` = WRONG + declined: printed, subject, key, ours, doubt, status, why.
- `## Key issues` section (list from 98.1; "none" when empty).
- No registry change: same kinds/names (config/report_kinds.json); pdf sibling unchanged.

### 98.4 Key line in solution report - deferred
Needs the key threaded into reporter.build_combined_markdown + new golden; the mismatch list (98.3) already
covers AC4. Out of scope unless user asks.

### 98.5 Free baseline (main, $0, dev line)
`exam report-pack <t81 runs x4> --exam dhqg2024 --key input/dgnl/De-thi-mau-DHQG-HCM-2024.answer.txt
--overlay <t82 run 20261107-014525>:64,65,66,67 --overlay-reason "<t82 reason>" --line dev` -> baseline
accuracy, saved as score-vs-key tsv; record numbers in phase-log.

### 98.6 Paid re-solve (main, real, cap ~$2-3.7) - AC2
- New `plans/dhqg2024/t98/run-all.sh` from t81 pattern with D fixed (see D1) and out `$D/run-<subj>`;
  inputs = existing `plans/dhqg2024/t81/e-*.md` (copied, sha256 equal). Key path appears nowhere in the script.
- Then 98.5 command on the new runs (+ overlay, see Decisions), `--line dev`; diff its score-vs-key.tsv
  against baseline (changed rows = engine drift). `publish --from dev --key FILE` only after user looks.

## Failure modes
| Failure | System response | Operator sees |
| --- | --- | --- |
| key has bad/dup/missing entries | scored as keybad/nokey, excluded from accuracy | stderr `key issue:` + md section |
| key has no letters | ValueError (l.129, unchanged) | error, exit non-zero |
| key file reaches solve | must not happen | 98.6 check: grep key path in t98 script/logs = 0; e-*.md sha equal |
| run over cap | solve stops at --max-cost-usd | solve-status rc != 0, partial; main decides |
| run-all.sh D path stale | outputs written to wrong dir | see D1 |

## Unit tests (tests/unit/test_explain.py, tests/unit/test_report_pack*.py or nearest existing)
- parse_key synthetic text with "Câu 1. A", "2. b", "Câu 3.C ", "Câu 4. I", dup "1. B", gap 5..6 then 7. D ->
  key {1:A,2:B,3:C,7:D}, issues bad_letter 4/I, duplicate 1/B, missing 5, 6.
- load_key output identical to parse_key()[0]; existing test_explain.py:247 still passes.
- _score_rows: issue printed -> keybad; accuracy excludes keybad/nokey (3 rows: correct, WRONG, keybad -> 50%).
- _summary calibration counts per doubt level sum to scorable; mismatch rows carry `why` from solution steps.
- _summary_md has sections Score, Per question, Calibration, Mismatches, Key issues.
- build_pack without key: file list and answer-table bytes unchanged (existing golden).
- Synthetic non-DGNL 3-question key end-to-end through build_pack (no pdf).

## Verification
| Item | Command -> expected | Tier |
| --- | --- | --- |
| 98.1 | `python3 -I -c "...explain.parse_key('input/dgnl/De-thi-mau-DHQG-HCM-2024.answer.txt')"` -> 119 keys, issues == [65 bad_letter I] | $0 |
| 98.2 | baseline pack: stderr `key issue: 65 bad_letter I`; score-vs-key.tsv row 65 result keybad | $0 |
| 98.3 | score-summary.md has the 5 sections; Accuracy denominators = 119 - nokey | $0 |
| 98.5 | baseline pack check passes (no missing/unregistered) | $0 |
| 98.6 | t98 runs rc=0 for 4 subjects, cost.tsv sum <= cap; key grep in t98 inputs/logs = 0; e-*.md sha == t81 | paid |
| tests | `python3 -I tools/run_tests.py --fast` green | $0 |

## Decisions (recommendations, main/user confirm)
- D1 Paths: t81/run-all.sh uses `D=plans/dhqg2024-t81` (stale; files now in plans/dhqg2024/t81). New script
  uses `D=plans/dhqg2024/t98`, rel paths, cd to repo root. Rejected: editing t81 script (history).
- D2 Printed 64-67: re-solve t82 `e-64-67.md` in the same paid run (cents) and overlay it, so one engine
  version scores all 120. Rejected: reuse old t82 overlay (mixes engine versions).
- D3 Câu 65: scored `keybad`, excluded; not guessed, not asked (user may fix the key file later).
- D4 Key line in solution report: deferred (98.4).

## Out of scope
Key line in learner solution report; new report kinds; engine/prompt changes.

## Defects
- DEF-1 (low) plans/dhqg2024/t81/run-all.sh:3 `D=plans/dhqg2024-t81` no longer matches the dir; rerun as-is
  writes elsewhere / fails on missing e-*.md. Fix via D1 (new script), not by editing the old one.
- DEF-2 (low) explain.py:83 load_key drops a non A-D letter silently (Câu 65 "I"); fixed by 98.1.
- DEF-3 (content, key file) input/dgnl/De-thi-mau-DHQG-HCM-2024.answer.txt:7 `Câu 65. I` invalid letter; user to confirm.

Nova

## Newer features kept
No-key packs stay byte-identical; publish/overlay/main-line behaviour (TASK-094..097) unchanged.

## Plan modes
No effect on single-source or pipeline plan files: only report-pack scoring/summary output changes (key-gated); solve inputs are untouched, the paid t98 run reuses the t81 exam files.
