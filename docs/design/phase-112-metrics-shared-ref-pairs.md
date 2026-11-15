PROGRESS: COMPLETE
SKILLS: design, token-efficiency

# Phase 112 - metrics shared_ref and pair n (draft for docs/design/phase-112-metrics-shared-ref-pairs.md)
Task: TASK-112 · REQ-0119 · Status: draft
Supersedes: phase-69-parsing-metrics.md:41 (shared_ref row). Source: phase-107-review-triage.md:31-32, work/TASK-107/handoff/design-pipeline.md:11,13.

## Premise
- 109-F002 confirmed: metrics.py:375 `want` = every gold id with the label; metrics.py:377 `got` holds only ids in `qs`. One unextracted sibling fails every correctly linked sibling as `unlinked`, though extraction already counts it `missing` (metrics.py:358).
- 109-F004 confirmed: classify skips ids absent in B (metrics.py:593) and never visits B-only ids; board_delta sets `n=mb["n"]` (metrics.py:660). `n` is only summed in pool (metrics.py:669) and printed in the verdict text (metrics.py:687); it never drives a verdict or exit code (cli.py:2356 tests only the verdict string).
- Both values are computed live on each `board`/`--structure-gold` call (cli.py:2190, cli.py:2337). Neither is stored in run-history.jsonl or any cache, so no cache key or history compat concern.

## Goal
- shared_ref scores only the link among extracted gold ids (user RAW-00337); a missing sibling shows only under extraction.
- board delta `n` = compared pairs (ids in both runs).

## Constraints
- No change to extraction/boundary/other metrics, to classify's lists, to verdict rules, or to output formats.
- Python stdlib only; no new inputs.

## Generality
Metric code has no exam-specific literal; covers every exam kind with a structure gold or a paired run. Tests use synthetic ids/passages (non-DGNL).

## Known incidents
none

## Plan modes
- single-source plan: no plan-file or result schema change; the board reads the same results.
- pipeline plan: same; no stage or cache touched (nothing here is cached).

## Design
### 112.1 shared_ref expected set limited to extracted ids (owner: metrics.structure_scores, metrics.py:374-379)
- Change metrics.py:375 only: `want = {x["id"] for x in gold if x.get("shared") == g["shared"] and x["id"] in qs}`. `got` (377-378) and the `why` label (379) stay.
- New row text for the phase-112 doc to quote (replaces phase-69:41):
  `| shared_ref | extracted rows with \`shared\` | {gold ids p in the exam: p.section==q.section and squash(parser._passage(p)) == squash(parser._passage(q)) != ""} ∪ {q} == {gold ids in the exam with the same \`shared\` label} | unlinked / overlinked |`
  plus note: "A gold sibling not in the exam is counted only by extraction (`missing`), never by shared_ref (RAW-00337)."
- Effect: a lone extracted member of a group passes unless overlinked (accepted: its missing siblings fail extraction).

### 112.2 board_delta n = compared pairs (owner: metrics.board_delta, metrics.py:656-661)
- metrics.py:660: `n=len({q["id"] for q in ma["questions"]} & {q["id"] for q in mb["questions"]})` instead of `mb["n"]`. classify unchanged. Docstring: "n = compared pairs (ids in both runs, 112.2)".
- pool (669) and verdict text (687) unchanged; they now sum/print pairs.

## Consumers (Grep shared_ref / board_delta / delta n over src, tools, tests, docs)
| Consumer | Change? |
|---|---|
| metrics.py:316 STRUCTURE_METRICS, cli.py:2190 structure gold line/JSON | no (same key, value only) |
| docs/guide/toolkit-reference.md:20 (lists metric names, no formula) | no |
| docs/design/phase-69-parsing-metrics.md:41,112 | no edit (DONE phase); superseded by phase-112 doc |
| docs/design/phase-63-engine-scoreboard.md:54 (`n=..` placeholder) | no (meaning now defined in 112.2) |
| metrics.py:669 pool, :687 verdict text, :740 board_kind, `board --json` kinds.*.delta.n | value only; no code change |
| cli.py:2356 exit code | no (verdict string only) |
| run-history.jsonl / reports | not stored there; no change; no old/new mix to tell apart |
| tests test_structure_scores.py:49,73, fixture structure_gold.json:683 (65_1 case, all 4 ids extracted, split sections -> still miss 1-4), test_structure_scores_qa.py:33 (2/2 kept) | no; must stay green |
| tests test_run_board.py:115,183, test_eval_stats.py:129 (equal-size runs, n not asserted) | no |

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| gold group fully missing but one id | that id scored vs {itself} | shared_ref pass; extraction `missing` for siblings |
| runs share no ids | n=0 | `same (within noise n=0 flips=0)` only if basis set; else `unmeasured` |

## Unit tests (tests/unit/test_structure_scores.py, tests/unit/test_run_board.py)
- test_t11_shared_missing_sibling (AC1): gold [{1,g},{2,g},{3,g}], exam 1,2 same section+passage -> shared_ref (2,2), miss []; extraction miss [{3,"missing"}].
- test_t12_shared_missing_sibling_unlinked (AC2): same gold, exam 1,2 different passages -> shared_ref (0,2), whys {"unlinked"}.
- existing test_t4_shared_overlinked (AC2 overlink) and test_t5_gold_set unchanged and green.
- test_board_delta_n_pairs (AC3): r(i)={"id":i,"answer":"A","reason":None,"key_ok":True,"status":"PASS"}; board_delta({"questions":[r(1)],"n":1},{"questions":[r(1),r(2)],"n":2})["n"] == 1 (was 2); swapped args == 1.
- test_board_delta_n_disjoint: A ids {1}, B ids {2} -> n 0; pool of AC3 delta twice -> n 2.

## Verification
| Item | command -> expected | tier |
|---|---|---|
| 112.1 | `python3 -I tools/run_tests.py --affected` -> t11,t12,t4,t5 pass, NEW 0 | unit |
| 112.2 | same run -> test_board_delta_n_* pass; `--fast` NEW 0 | unit |
| AC5 | main: `board` on stored plans before/after (free, no AI) -> diff only in `n=` of verdict text and shared_ref rows of groups with a missing sibling | free local |

## Decisions
- want ∩ exam ids (RAW-00337) - rejected: drop shared_ref for partial groups (loses link check) - user choice.
- n via id-set intersection in board_delta - rejected: counter returned from classify (phase-109 report Fix; widens classify's output for one consumer).

## Out of scope
Other phase-109 findings; extraction metric semantics; phase-69 doc edits.

## Defects
none beyond 109-F002/109-F004 (confirmed against source above).

Nova

## Coordinator check (2026-11-16)
grep shared_ref over plans/ and reports/ = 0 files: no stored value uses the old formula. Supersedes the shared_ref row of docs/design/phase-69-parsing-metrics.md:41 (user decision RAW-00337).
