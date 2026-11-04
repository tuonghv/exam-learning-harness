# Report phase 77: answer-driven learning loop (TASK-077; REQ-0084, RAW-00202)

Verdict: adopted. When the user supplies official answers, the engine can now explain every wrong or flagged answer with deterministic, free checks and measure the gain on a held-out exam, so the deep dive no longer depends on manual work.

## What was built
- `run-stats explain RESULT_DIR --exam FILE --key FILE --pdf FILE` (no AI call): per wrong answer it checks extraction (stem and options in the prompt against the PDF text of the source pages; thresholds fwd 0.85, rev 0.63, reliable share 0.8, set from the saved data), context delivered (shared passage, group table, sibling answers, carrier pages in the call that produced the answer), reply path (malformed or multi-object replies, image-only source, text/image disagreement, adjudication, second sample), solver signals (evidence quote found in the prompt, an alternative reading named by the solver) and assigns a primary cause by a documented priority. The key is for scoring only: the output holds numbers, causes and flags, never key letters or question text (audit: 0 leaks across all output forms; the audit script catches planted leaks).
- `run-stats gain --spec FILE`: accuracy before and after a change on the learn exam and a held-out exam, over all keyed questions (declined count as not correct), Wilson intervals, "no measurable change" when fewer than 5 answers changed; both on the board (`--explain`, `--gain`).
- The usage-limit message ("hit your 5-hour limit", "reached your limit", "limit reached" with a reset time) now stops the run instead of producing fake wrong answers (Science 112 in 2026 run 3); a mathematical "limit" in an answer does not.
- Standing process: `docs/guide/workflow-roles.md` section 10.

## Replay on the saved runs (numbers and causes only)
All 7 wrong answers of the 2025 run match the causes found by hand, and the English multi-object reply path is found for 9 questions. For 2026: 24, 63, 65 and 112 match; 38 comes out "unknown" (the tool declines to guess because the 2026 English PDF prints that item's options as bare letters and the text-layer guard fails); the tester's hand check calls it solver reasoning. Math 2026 Q65 and 2025 Q67 are labelled solver reasoning, not key oddity: a key oddity needs a recorded independent recomputation.
Gain: 2025 learn exam 113 to 111 of 120; 2026 held-out 36 to 36 of 43 (4 fixed, 4 regressed): no measurable change. An earlier figure of 32 to 36 of 39 dropped the declined questions and was withdrawn (TASK-076 report corrected).

## Limits
The regression-set gain is not wired into the gain spec; one held-out exam, n=43; the extraction reverse check does not separate half-cut stems on every subject.

User instructions honoured: RAW-00199, RAW-00202.
