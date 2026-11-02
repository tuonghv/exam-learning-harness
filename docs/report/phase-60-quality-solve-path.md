# Report phase 60: quality solve path, slice A (TASK-060; REQ-0066)

Verdict: slice A adopted; the image-scope slice (60.4-60.6) is open and goes to a follow-up task. From saved real runs 42 non-pass questions were tagged by cause: 23 QA false alarms, 6 flawed source or count mismatch, 5 cut questions, 3 OCR/parse, 3 missing visual, 2 solver reasoning, 0 passage link. The real runs contained no proven wrong answer (the only keyed exam scored 4/4 and 22/22; DGNL has no key, so its rows are non-passes, tagged weakly). The largest, cheapest cause was therefore fixed first, at no cost.

## What changed (all free, no prompt change)
- 60.1 `option_for_value`: a numeric multiple-choice answer given as the option value maps to the option letter, only when the answer holds one number (a trailing parenthetical rounding note is ignored); `;`, fractions, sqrt, `^` or several numbers return nothing (a wrong letter is worse than none).
- 60.2 `run-stats recheck RESULT_DIR --exam FILE`: re-runs the deterministic checks on a saved run; column `no_check_fails` (not proof of correctness). Saved Science run: 7 cleared, q17 stays failed; Vietnamese q20 stays failed.
- 60.3/60.7 `needs_review_why` reason code on flagged questions and metrics rows via `run-stats stats --refined FILE`.

## Evidence (work/TASK-060/evidence/, not published: evidence_required is off)
Full suite 1144 tests, only the known baseline failures; solve/retry/QA prompts identical on 15 inputs; mutations on the letter mapping and recheck killed. Found and fixed: recheck cleared everything because saved results lack `answer_status` (tester D1), duplicate `--refined` on review-pack (D4), multi-number mapping "3; 5" (verifier), over-strict digit rule (coordinator, 3 vs 7 cleared).

## Limits
Mapped letters were not compared with an answer key. An option such as "H2O" can match the answer "2" (low). The image path for cut/declined and doubtful questions (60.4, 60.5), adjudication (60.6) and the paid checks P1-P3 (caps 2.50 USD total, decided by the coordinator inside caps, RAW-00186) are not done.

User instructions honoured: RAW-00183, RAW-00184, RAW-00186.
