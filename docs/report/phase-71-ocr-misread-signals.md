# Report phase 71: OCR single-character misread signals (TASK-071; REQ-0065)

Verdict: adopted on synthetic data, with the real-scan false-alarm rate still unmeasured. Three cheap signals now mark OCR questions that carry a single-character misread (e.g. `So` read as `$6`) so they do not reach the solver unmarked: `low_conf` (tesseract CLI TSV per-word confidence, `ocr_conf` default `auto`), `token` (implausible glyph shapes; weak shapes count only when the TSV confidence is low) and `option_parity` (a soft structure flag on the board). Signals only mark; they never correct text and make no AI call. The threshold comes from an offline sweep with a 0-false-alarm rule: floor 60, margin 0. Without the tesseract binary `low_conf` is skipped with an info warning.

## Measured (offline, TASK-051 synthetic families plus the new clean family Cm)
0 false alarms on A, B, D and on 18 clean unaccented questions (Cm). Unmarked wrong answers on family C fell from 15 (phase 51) to 10 with the strong token shapes and to 3 with `low_conf` plus weak tokens; A and B did not improve. `option_parity` flagged 3 wrong questions and no correct ones.

## Safety
New process call in `adapters/pdf.py`: list argv, no shell, language only vie/eng, timeout, page as PNG pixels on stdin, every failure skips gracefully; the guard test allowlists only that file. 1397 tests, only the 4 baseline failures; 8/8 mutations killed.

## Limits
The whole gain is on family C, where every accented word is misread, so false alarms on correctly read accented text are unmeasured; floor 60 sits just below the confidence-70 level where family A shows 4 false alarms. Real scans are unmeasured: the first number to measure on the user's labelled pages (REQ-0040) is the `low_conf` flag share; fallback floor 50 or `ocr_conf` off. The refined route is deferred (phase-51 G4). DOCX was not run in QA (python-docx missing here).

User instructions honoured: REQ-0065 follow-up of phase 51.
