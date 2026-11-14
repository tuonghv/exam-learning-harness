# Phase 104 report: checker scores a bad key letter like the engine

Task: TASK-104 · REQ-0112 (RAW-00325) · design `docs/design/phase-104-checker-bad-key-letter.md`

- Action: `tools/check_report_pack.py` now applies the engine's bad_letter key rule (reimplemented, no engine import,
  so it stays an independent oracle): a question whose key is not A-D leaves the scorable total, gets a
  `score-vs-key keybad` check and a `KEYISSUE <n> bad_letter <tok>` line that is not a failure.
- Result: dhqg2024 main + t81 packs 64 checks 0 failed (were 2 failed), `KEYISSUE 65 bad_letter I`, total 105/119;
  dgnl2025/dgnl2026 0 failed; fast suite 1946 tests KNOWN 4 NEW 0; the new test fails on the old checker.
- Decision: a known key-file defect is reported, not counted as a pack failure, so a red checker means a real problem.
  Next: TASK-105 (tracked rebuild recipe + `exam rebuild-reports`).

## Defects
- input/dgnl/De-thi-mau-DHQG-HCM-2024.answer.txt: `Câu 65. I` is not a valid answer letter (user-supplied key; unchanged).

Evidence: `docs/report/evidence/TASK-104/verify.md`
