# Phase 61 - Image scope for cut/declined and doubtful questions (TASK-061)
Task: TASK-061 (REQ-0067) · Status: designed. Full design: `docs/design/phase-60-quality-solve-path.md` items 60.4-60.6 (this phase implements them as written; read that doc first).

## Goal
`--image-scope declined|doubt` (default `flagged` = today, byte-identical): cut/marker-declined questions (defect D2, engine.py:126) and doubtful answers reach the one capped page-image call; a second read never makes PASS; optional `--adjudicate` for image_differs.

## Plan modes
Single-source and pipeline plans unchanged by default. Only runs with `--pdf` and `--image-scope` != flagged change; the plan run captures scope and image calls as in phase 59. Cross-solve unaffected.

## Design
- 61.1 (= 60.4) scope `declined`: candidates = flagged ∪ skip ∪ solver_declined ids; skip ids first; same page/key/cap rules.
- 61.2 (= 60.5) scope `doubt`: declined ∪ answered ids with reasons solver_uncertainty_not_low, reviewer_unsure, reviewer_disagrees, no_review; lowest priority under the page cap; finding `image_agrees` (status unchanged).
- 61.3 (= 60.6) `--adjudicate`: only for image_differs ids, one text call, +1 call_cap only with the flag; status stays UNCERTAIN `needs_review: adjudicated`.
- 61.4 metrics: `image_scope`, `image_agrees`, `image_differs` rows.

## Unit tests
Design doc phase-60 "Unit tests" 4-9 (mock LLM, synthetic text): skip ids reach the image check only with scope declined; default scope prompts byte-identical (golden 15 inputs); doubt ids get agrees/differs; page cap respected; adjudicate off by default.

## Verification
Free: unit suite vs baseline names, `--dry-run` shows scope and page list. Paid P1-P3 (phase-60 §Paid items): coordinator runs inside caps (0.60+0.30, 0.80+0.50, 0.30), results recorded in the REQ.

## Failure modes
Image unreadable or absent: text result unchanged plus finding (phase 59 rule G1); cap reached: remaining ids keep text result; render failure: finding, no decline change.

## Decisions
Default scope stays `flagged`; slow path is opt-in per run. 61.3 is built but only exercised by a paid run if P2 shows a differ.
