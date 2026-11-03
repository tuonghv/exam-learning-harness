# Report phase 63: engine scoreboard (TASK-063; REQ-0069, RAW-00188)

Verdict: adopted (63.1-63.5). `exam.py run-stats board` prints, per exam kind, coverage next to quality, cost and the change against a baseline, using only saved runs and history (no AI call). Coverage alone is never `better`; a run without key or QA reference prints `quality unmeasured` and verdict `unmeasured`; a coverage rise with more wrong answers is flagged. Existing `stats`, `compare` and `trend` output is byte-identical (golden).

## Fixes from the statistics review (RAW-00189, phase 64)
The board headline counts every keyed question as the denominator, so refusing cannot raise it: 20 answered of 30, 16 correct -> `16/30 (53% of all keyed)`, not 80%; a declined question later answered wrong is `wrong_new`. Review packs are scoped per exam (`[SHA_PREFIX|EXAM_ID=]FILE`); an unscoped pack with more than one exam exits 2 (ids no longer collide across exams). `scorer.py` is untouched; the quality fields are additive.

## Evidence (work/TASK-063/evidence/, not published)
1225 tests, only the baseline failures; 5/5 mutations killed; hand-counted 30q, 2q, 100q and shared-id cases; read-only board on the saved DGNL and trial runs: DGNL kinds print `unmeasured` (no key), as they should.

## Limits
The key and precision path was not exercised on a real keyed history line (unit tests and one keyed mock run only); the denominator assumes the key covers unanswered questions; `noise()` is still loose at small n (TASK-064). The keyed regression set (63.6) is REQ-0072.

User instructions honoured: RAW-00188, RAW-00189.
