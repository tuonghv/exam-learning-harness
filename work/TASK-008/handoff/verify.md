PROGRESS: COMPLETE
SKILLS: verify, crosscheck, token-efficiency
Verifier: Argus. Method: re-solved English 002-005 from inputs before reading keys; checked Literature quotes by reading against passages (manual substring check, no script run; evidence/examples-check.txt and suite.txt not re-read).

## English (independent re-solve)
- 002 vocab: I chose A take; key A (examples/english/expected-002.md:5). MATCH
- 003 reading detail: I chose B (8h vs 4h sleep, same list); key B (evals/keys/english/expected-003.md:5). MATCH
- 004 ordering: I got b-d-a-e-c (Linh/She/the choice; However/at first; Because of this; Now after courses); key b-d-a-e-c (expected-004.md:5), permutation of a-e. MATCH
- 005 grammar: I chose A when (Hardly...when); key A (expected-005.md:5). MATCH
- Each has one correct option and a reason per distractor (003:16-19, 005:16-19, 002:16-19); 004 gives a reason per sentence (16-22) and an adjacency check.
- Skills covered: grammar 005, vocab 002, reading 003, ordering 004.

## Literature
- Passages are short original Vietnamese verse/prose, not known works (examples 001-002, evals 003-005).
- Each key has 3 accepted readings, each with a quoted evidence line; every quote is a verbatim substring of its input passage (001 lines 20,24,22; 002 lines 18,20,22; 003 lines 20,22,24; 004 lines 22,20,24; 005 lines 17,19,21).
- Rubric: content 4 + evidence 2 + structure 2 + language 2 = 10, "Tổng: 10 điểm" (e.g. expected-003.md:38-43).
- Inputs hold no key text (only the question and passage).

## AC verdicts
- AC1 VERIFIED (all four skills, one correct option, reason per distractor).
- AC2 VERIFIED (key b-d-a-e-c is a permutation of a-e; the segment links hold as I re-derived them. I did not run the checker myself).
- AC3 VERIFIED (>= 2 readings with quotes, rubric with 4 criteria that add to 10).
- AC4 VERIFIED (original, self-contained, quotes verbatim; checked by hand, not by script output).

## Defects
- D1 minor: the line "Any other reading is accepted only if it is supported by quoted evidence from the passage." is present in the few-shot keys (examples/literature/expected-001.md:30, expected-002.md:29) but missing from the eval keys 003-005. Impact is low: the eval keys are never shown to the solver, the three readings and the "accepted only with quoted evidence" rule are already in the rubric, and the line is in the few-shot examples. Suggest adding it to keep the set uniform. It is not blocking.
- D2 minor: in evals/keys/english/expected-003.md:16, option A reads "never says the second group studied for less". The passage does not give the second group's study time, so the reasoning holds, but "the passage does not say how long the second group studied" would be more precise.
- No major defects.
