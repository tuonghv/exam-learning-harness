# Report phase 35: extraction accuracy benchmark, tier 0 (TASK-035; REQ-0025)

Verdict: adopted as a measuring instrument, not as a measurement. `python3 -I scripts/exam.py extract-eval GOLD EXTRACTED [--out DIR]` scores extracted questions against gold: per-field and overall exact-match accuracy, verified-subset precision, needs_review rate, Wilson 95% intervals and the sample size needed for a 99.999% claim. It says plainly that the claim is not made.

## What it proves and what it does not
- Proves: the metric works and bites. On the corrupted fixture overall accuracy drops from 20/20 to 14/20 (Wilson 48.1%-85.5%), verified precision 14/19; 99.999% needs 299,572 error-free questions (computed, not hardcoded).
- Does NOT prove real extraction accuracy: the gold is 20 easy synthetic questions and the extractions are hand-corrupted fixtures (verifier residual risk). Real numbers need REQ-0039 (PDF level, then the user's labelled pages).

## Design choices that protect quality
Exact = NFC plus whitespace collapse only (fold/similarity deliberately not used: they would hide diacritic, case and sign errors); gold loader rejects answer/solution keys; gold lives in `evals/extract/gold/`, which check-examples and benchmark do not scan; no accuracy gate (REQ-0024 owns gating); no network, subprocess or paid call.

## Evidence (work/TASK-035/evidence/)
`final_unit_suite.txt` 546 tests, only the 3 known failures; `final_base_unit_suite.txt` the same 3 at the base commit (531 tests, pre-existing, examples/dgnl pairing); `final_extract_eval_tests.txt` 15 tests OK; `final_cli_corrupted.txt` CLI output; `final_diff_protected.txt` no change to schemas, solver, engine, prompts, config, settings; tester oracle `t35-oracle-vs-cli.txt` (independent recompute matches), `t35-adv.txt` 15/15 adversarial, 4 mutations caught (fuzzy exact, swapped Wilson, dropped key rejection, ...); verifier `work/TASK-035/handoff/verify.md` AC1-AC5 PASS.

## Decisions to review
- REQ-0025 AC1 reworded from "synthetic PDFs" to "synthetic gold JSON"; the PDF part is REQ-0039 / TASK-036 (queued).
- Design corrected 299573 -> 299572 (Titan's recompute; checked by the coordinator: ceil(299571.73)).

## Limitations
One low note from the tester: no corrupted-fixture test covers a case or U+2212 sign difference end to end (the unit test for `canon` does).

User instructions honoured: RAW-00128, RAW-00129, RAW-00133 (quality over speed), RAW-00141.
