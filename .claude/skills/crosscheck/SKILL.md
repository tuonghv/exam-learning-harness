---
name: crosscheck
description: Independent cross-checks (oracles) that prove a pipeline's numbers and decisions are right without trusting the code under test - recompute with jq/grep/awk from the source files, reconcile counts end to end, diff decisions, prove the test bites, and report mismatches as grep-able TSV. Load when asked to QA, verify, cross-check or "make sure the counts are correct", when a coder claims a count or coverage result, or before numbers go to the user.
---

# Cross-check (independent oracle)

User rules: "you should have a solution to cross check; maybe the script is not correct, but grep can check" (RAW-00254);
"count, grep to compare first" (RAW-00251); report numbers only when engine and oracle agree.

## Principles
1. **Independent path.** Recompute from the rawest file you can reach (the tool's own SARIF/JSON, the raw log, the
   manifest), in plain bash + jq + grep/awk. Never import or call the code under test. If you must reuse a data
   table (api_map.json), read it with jq, not through the code's loader.
2. **Reconcile end to end.** Every stage boundary has an equation; write it down and check it:
   `raw = kept + labelled_out + merged_dup (+ capped)`; `rows = records' b_ids ∪ out[]` (set equality both ways);
   `matrix total = records`; `items ⊆ in/needs_ai records`. A single unexplained difference is a FAIL, not noise.
3. **Sets, not just counts.** Equal totals can hide a swap. Compare id sets with `comm -3` or
   `jq -n --slurpfile a A --slurpfile b B '($a[0]-$b[0]), ($b[0]-$a[0])'`, and print both differences.
4. **Diff decisions row by row.** Recompute category/decision per row from the data tables and emit a TSV
   `id tool rule cwe engine oracle`; an empty TSV is the pass condition.
5. **Prove the check bites.** Mutate a fixture (delete one row, flip one category, add a removed-tool row)
   and show the oracle FAILs. A check that has never failed proves nothing.
6. **Like for like.** Compare numbers from the same runner, plan, stage and config; label every number with
   its source path. Never mix a trial/compose count with a runner count (lesson 2026-10-01).
7. **Grep sanity on outputs.** No code or secret text (`snippet`, `lines`, `code`, `Secret` keys), no removed tool,
   no SCA row outside `dependencies`, no empty required field.

## Output
- One line per check: `<check>: PASS|FAIL|SKIP <counts> <evidence path>`; mismatch TSVs under `work/<T>/evidence/`.
- Save each run with `.claude/scripts/save-evidence.sh <name> -- <cmd>`.
- A FAIL names the stage, the equation and the first differing ids. It is a finding for the coder, never something to
  "adjust" in the oracle until it passes.

## Exam content oracle
Each check runs without the generator's code and reports one TSV row per failing item (an empty TSV = PASS).
- Maths/Physics: recompute every key from the item text (stdlib `python3 -I -c`, `fractions`/`decimal`); compare the value,
  the unit (SI, as stated) and the rounding (stated places or significant figures).
- English: re-apply the named grammar or vocabulary rule to each option; exactly one option may pass.
- Literature: every quote is a verbatim substring of the passage (`grep -F`) and its attribution matches.
- Leakage: no eval key string appears in eval inputs or few-shot files (`grep -F -f keys inputs`); empty = PASS.
- Format: each expected file has Final answer, Solution, Explanation, Verification (`- Check:` lines, `Status: Verified`), Grading.

