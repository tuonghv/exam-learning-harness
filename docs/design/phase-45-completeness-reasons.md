# Phase 45: completeness reasons (TASK-045; REQ-0049)
Source: docs/design/phase-43-question-completeness-gate.md section 43.2 and defects D2 (unreadable not stored) and D3 (same-id join drops continued_pages/cut). Text from 43.2:

### 43.2 Completeness reasons (owner: refcheck.incomplete_reasons) - tier 0, $0
- `formula_unbalanced`: opens `([{` != closes `)]}` (counted together, so half-open intervals `[a;b)` stay balanced) or odd unescaped `$` in text+options; `trailing_operator`: text ends with `= + - × ÷ / ^ \` and no options. Only for questions with `cut`, `continued_pages` or last-on-page (refined `page` max), to keep false declines low.
- `merge_suspect`: a line inside the stem matches segment._Q with a number != own id, or two A-D option runs.
- `unreadable`: refine stores `unreadable: true` (refine.py:349-354, optional field) -> reason (fixes D2).
- Options: A reasons in refcheck (chosen: one function, render-time so old files get it, reuse T41 path). B a separate validator module (duplicate). C AI review of every question ($ per question, non-deterministic).
- Risk: math stems with unpaired bracket by design -> scoped to page-end questions; measured by 43.6 false-decline count.

## Defect fixes included
- D2: refine stores `unreadable: true` as an optional field (refine.py around the reply validation) and `incomplete_reasons` returns `unreadable`; a question rendered with that reason is marked `[Incomplete: missing_text unreadable]` and declined like the others.
- D3: api.py same-id join (~:119-122): the joined question keeps `continued_pages` from the parts and `cut` of the LAST part (the first part's `cut` is resolved by the join), so a resolved split question is not declined as cut_unresolved.

## Plan modes
Render-time reasons apply to PDF vision-refined questions and (options/referenced/formula) to segmented questions of the text route; no change to solve prompts or result schema; old refined.json load.

## Tests-first list (tier 0, synthetic placeholder text)
1. formula_unbalanced: `( [ {` opens != closes counted together; half-open interval `[a;b)` stays balanced; odd `$` flagged; only for cut/continued/last-on-page questions (a mid-page question with an unbalanced bracket is NOT flagged).
2. trailing_operator: text ends with `= + - × ÷ / ^ \` and no options -> flagged; ends with a normal sentence -> not.
3. merge_suspect: a line inside the stem starting like another question number (segment._Q) != own id, or two A-D option runs -> flagged; a numbered list inside a stem (1., 2.) that is its own sub-list: documented limit.
4. unreadable: reply `unreadable:true` stored -> reason; absent -> unchanged; old refined.json unchanged.
5. same-id join: part 1 cut + part 2 continued -> joined question not cut_unresolved and keeps continued_pages; part 2 cut -> stays cut.
6. no false declines: every complete synthetic fixture and the real refined3 render (printed numbers) get no new reason except documented ones.
7. engine decline reason string includes the new reasons.
## Verification
Tier 0: unit suite; real read-only regression on work/dgnl-real/refined3.json and work/TASK-040/real merged-refined.json: list questions newly carrying a reason by printed number; any clean question newly flagged is a defect to fix (target 0). Independent oracle by the tester for the bracket/dollar balance on generated strings.
## Risks / out of scope
Math stems with intentionally unbalanced brackets (scoped to page-end questions); AI review; recovery (TASK-047).
