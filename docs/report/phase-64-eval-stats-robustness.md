# Report phase 64: evaluation statistics robustness (TASK-064; REQ-0071, RAW-00189)

Verdict: adopted (64.1-64.7). Review brief: `tmp/AI-Engine-Evaluation.md`. Confirmed gaps and their fixes:
- Refusing raised the key score: `scorer` now scores non-answered keyed questions 0, so the headline is over all keyed questions (30 questions, 20 answered, 16 correct: 16/30 = 53%, not 80%). Declined open-rubric or unkeyed items stay out of the denominator (verifier D1 fixed). The old answered-only figure is still printed.
- `noise()` called 4-0, 5-0, 7-1, 9-2, 11-3, 12-4 a signal although the exact sign test gives p between 0.057 and 0.125: now an exact sign test; 3-1 and zero flips print `insufficient`; no key and no QA prints `unmeasured`, never `better`.
- Averaging per exam let a 2-question exam weigh as much as a 100-question one: kind aggregates are pooled by question, with a Wilson interval.
- Exploratory runs looked official and baselines ignored the engine version: history lines carry a tier (official = keyed regression set) and the baseline pairs the same version key; board keys are `tier|kind`.

## Evidence (work/TASK-064/evidence/, not published)
1245 tests, failures only the 4 known baseline names; independent p-values and Wilson intervals match code and design; 6/6 mutations killed (answered-only denominator, normal approximation, tier filter, version-agnostic baseline, always decisive, per-exam mean); saved DGNL compare and board print `unmeasured` / exploratory, never `better`.

## Limits
Runs written before this task must be re-scored to get the new headline (an old declined item cannot be told from an open-rubric decline). The official tier is empty until REQ-0072 scores the keyed regression set. The benchmark regression rule (G9, `benchmark.py`) is untouched. No real keyed run yet.

User instructions honoured: RAW-00189.
