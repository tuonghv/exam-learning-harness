# Report phase 37: DGNL sample scored against the official answers (TASK-037; REQ-0040)

Verdict: first real accuracy number. The saved run 3 of the 2026 DGNL sample scores 111 of 120 (92.5 percent; 94.9 percent of the 117 answered): Vietnamese 26/30, English 29/30, Math 27/30, Science 29/30 (22/30 with strict letter matching: 7 Science answers were given as the option value, all equal to the keyed option, and the format check wrongly flagged them; phase 60 maps them). Run 2 on Vietnamese, English and Science combined was 70/90 (78 percent); run 3 is 84/90.

## What the numbers say
- Every answer in every run is UNCERTAIN (`no_independent_check`); PASS never fires, so correct and wrong answers look the same: the 5 wrong answers carry only low or medium solver uncertainty. This is the biggest weakness: REQ-0079.
- The current engine on the 9 worst questions (0.325 USD): Vietnamese 10, 14, 23 (declined before) and Math 66 now answered correctly (window recovery and the page-image retry). Still wrong: Vietnamese 24 (solver reasoning, subjective item; text matches the PDF), Math 63 (solver reasoning: "gần nhất" means nearest option and the solver rejected a non-exact value: REQ-0080), Math 65 (likely a key oddity: the table equals the PDF text, 8 distinct edges give option A, the key says D; page image not viewed: please check). English 38 and Science 112 were not re-run (Science 112 is a rate-limit message in the saved run: an infrastructure failure). Projected: 115/120 (95.8 percent).

## Evidence (work/TASK-037/evidence/dgnl-score.txt, plans/dgnl-retry/, not tracked)
Per-run table, mapping by option text (Vietnamese +0, English +30, Math +60, Science +90), cross-checked by an independent strict-letter recount. The answer list stayed in `input/dgnl/` (untracked), used for scoring only; only counts and question numbers were recorded.

## Limits
One exam, one model. The Math offset matched 8 of 30 questions by text (symbol-heavy options), so the Math rows are likely but less certain. Extraction-only gold (extract-eval) was not provided: REQ-0078.

User instructions honoured: RAW-00197.
