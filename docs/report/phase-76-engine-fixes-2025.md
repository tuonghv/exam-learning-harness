# Report phase 76: engine fixes from the 2025 DGNL scoring (TASK-076; REQ-0083)

Verdict: the fixes remove real defects, but no accuracy gain is measurable: the effect is within run-to-run noise. Stated plainly, as the user asked for "stats gain after learning the answers": learn exam (2025 sample, where all fixes were found) 113 of 120 before, 111 of 120 after; held-out sets unchanged.

## What was fixed (each traced to a file and line, found by checking each wrong answer against the PDF)
- 76.1 A reply holding several JSON objects (the model corrected itself) failed to parse: `extract_json` now takes the last valid object that passes the schema (fenced or not), never an earlier retracted one. This put 9 English questions onto the image-only route and flipped printed 59.
- 76.3 A false `missing_text` flag: figure sharing keyed on the question's first line, which was the "Source pages" line. Over 367 questions only Science 111's flag changed.
- 76.4 Context not delivered: a group table stored on the first member (Science 99) never reached members 100-102, so a slice of 101-102 lost it and its page (101 starts on p17, the table is on p16). Group figures are now shared once per group inside the Passage, with the carrier's pages unioned into Source pages. 16 group members change in the 2025 refined doc; nothing outside a group; 295 existing exam files give identical solve prompts.
- 76.5/76.6 The adjudication prompt had no options and the adjudicator answered from outside knowledge: it now carries A-D and a text-first rule. `source: "adjudicated"` is set and accepted by the schema and the report.
- 76.2 Text/image disagreement: the conflict set now includes FAIL rows and tentative text. Adjudication ran on 3 questions in the full re-run: 0 of 2 real conflicts fixed and 1 correct answer changed to a wrong one (printed 27). It is therefore opt-in again (`--adjudicate`); the measured result overrode my first decision to make it the default.

## Measured (answers used for scoring only; counts and question numbers recorded)
- Learn exam, 2025: 113 to 111 of 120. English 59 fixed; 17 and 39 flipped (about 5 percent of answers flip between identical runs); 27 harmed by adjudication.
- Keyed regression set (held-out): 15 pass, 0 fail, 3 uncertain, identical verdicts on all 18 items.
- 2026 slice with refined text (held-out, 43 questions): 36 to 36 (4 fixed, 4 regressed; checked by hand in TASK-077). The 4 regressions are English 57-60, declined with missing_text because the passage start is not in the refined pages (a slice artifact; the engine refuses instead of guessing). The 4 fixes (Vietnamese 10, 14, 23, Math 66) come from the earlier window and image-retry work, not from this task. Dropping the 4 declined questions would give 32 to 36 of 39, but that choice is mine and flatters the result: the honest figure is 36 to 36 of 43.
- Spend: about 4.0 USD.

## Limits
One run each; n of changed answers 1-4; a noise baseline (same run twice, about 1.7 USD) would size the noise. Math 65 (2026) and Math 67 (2025) may be key oddities. The remaining wrong answers are mostly solver reasoning on subjective items (Vietnamese 16, English 60, Science 107).

User instructions honoured: RAW-00199, RAW-00202.
