# Report phase 70: route-B structure and generic dev prompts (TASK-070; REQ-0070)

Verdict: adopted. Slice B of the generality work (phase 62). The cross-solve route-B image prompt no longer fixes "Part I 1-12, Part II 1-4": `cross.structure_hint(text, n)` builds the span text from the route-A headings only when everything is consistent (at least 2 parts, one heading word, numbered 1..k, each heading after a blank line, spans sum to the question count); otherwise it uses the generic clause "Printed numbering may restart per part or section; count continuously...", so it never states a wrong span. The dev prompts (`system.md` and `lang/vi/system.md`, `verification/verify_answer.md` and `lang/vi/...`, `exam/solve.md` and `lang/vi/...`) no longer fix "Vietnamese Grade 12 ... Mathematics, Physics, English, Literature"; subject, level and language come from the exam header. The release channel (`prompts/releases/`) is untouched (diff empty, 114 inputs byte-identical).

## Real checks (paid, coordinator inside caps, RAW-00186; about 1.27 USD in total)
- Cross-solve on the trial exam (22 questions): agree 20, needs_review 2 (before: 19 and 3), 0.313 USD; identical answer values on all 22, only the formatting of true/false and decimals differs; the two remaining reviews are Q10 and Q18 (route A declines them, as before). This exam has no part headings, so the generic clause was used and still produced the right continuous numbering.
- Regression set on the dev channel (new wording): pass 14, fail 1, uncertain 3, 0.707 USD. The only new FAIL, physics/003 `check_failed: quote` with the correct answer, did not repeat: 3 of 3 PASS on the dev channel and 3 of 3 on release (a quote-check flake). Together with the earlier malformed-output flake, 2 flakes in 36 item-runs.

## Limits
The heading-derived hint was tested on synthetic text only; real exams whose headings lack a preceding blank line get the generic clause (safe). One exam, 3 items per official kind: no accuracy claim. `genexam.md`, `genexam_qa.md` and `subjects/literature.md` still fix a subject (out of scope). A flake rate of about 5 percent per item-run means a single flip needs a repeat.

User instructions honoured: RAW-00186, RAW-00187.
