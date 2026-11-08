# Phase 93 report - readable wording instead of raw `none` (REQ-0100)

Format change (cross-check this):
| Where | Old text | New text (vi) |
|---|---|---|
| answer of a declined question | `Đáp án: none` | `Đáp án: chưa có đáp án (solver từ chối)` |
| evidence | `Bằng chứng: none` | `Bằng chứng: không có (chưa có kiểm tra nào đạt)` |
| per-question score | `Điểm: - / - (none)` | `Điểm: chưa chấm` |
| metrics line of a pack without a key | `accuracy: none` | `accuracy: no key` |
English reports use the English equivalents (no phrase contains `none`).

- Result: the solution report (per subject, combined, pdf: one code path in `reporter._question_block` and `metrics.py`) prints localized phrases at render time. The data keeps its own values: `result.json`, answer-table tsv, score-vs-key, answer-sheet md are unchanged; `result-data` differs only by `engine_git`.
- Current runs: DGNL 2026 `reports/dgnl2026/f/run-20261108-061114/` (replaces `run-20261107-221047`, kept); DHQG 2024 `reports/dhqg2024/t81/run-20261108-061132/` (replaces `run-20261108-055609`, kept). Both rebuilt at $0 with `exam report-pack`.
- Measured: `none` words in the solution-report md: DGNL 256 -> 0, DHQG 284 -> 0; in the new pdfs 0 (old pdfs 126 and 140). Same content: DGNL 120 questions (119 answered, 1 declined, 113 correct), DHQG 120 (111 answered, 9 declined). Pack checkers 64 and 53 checks, 0 failed. Gate `--full`: ran 1864, new=[], known=4. `test_report_wording` 12 tests (8 fail on the previous code).
- Open (low): the confidence tier name `none` (only with `--confidence`, `metrics.py:523`) is kept as a defined tier; the DGNL per-question score says "chưa chấm" even though the pack has a key, because per-question scores are computed at solve time without the key (the key-based score is in score-vs-key).
- Evidence: `work/TASK-093/evidence/` (untracked).
