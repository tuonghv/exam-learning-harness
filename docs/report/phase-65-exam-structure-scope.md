# Report phase 65: exam structure and scoped context (TASK-065; REQ-0073, RAW-00192)

Verdict: adopted, stage 1 plus 65.3 and 65.5. Review brief: `tmp/Exam-Structure-Context.md`. The review ran 12 synthetic probe cases against the real parser; the saved real runs show 0 of 42 passage-link failures, so no DGNL accuracy gain is expected. The gain is for other exam kinds and for stopping silent text loss.

## Confirmed defects fixed
- P1 an instruction carried into the next section when numbering restarted: ranges are now scoped to their section (65.1).
- P2 a question's own instruction inside a range was deleted: it now leads the question text (65.2).
- P10b/P11 `A.`/`B.` lines in headings or passages were read as options, failing validation or emptying the passage: options are read only after `### Question text` (65.6); enumerated headings (`I.`, `B.`, `3.`) build a section stack, so the section path keeps its parent heading (65.5; the DGNL output changes only in the `Section:` lines, golden updated by name); range words match any case (65.3).
- Structure flags (`structure:` rows in the assembly sidecar, `WARN: structure:` at ingest) report ambiguous cases instead of guessing (65.8).

## Safety found by QA
The tester found a critical regression in the first version (an upper-case option bank at the start of a context was peeled as headings, deleting the choices); fixed over two rounds: a label line followed by another label line is never a heading (in doubt it stays an option with an `ambiguous_heading` flag), and the parser fallback takes a trailing option bank after blank lines and accepts A-E, a-e and `A)` labels. Final sweep: 79 bank shapes across 7 positions, 0 choices lost; blank-line banks keep A-D as in the baseline.

## Evidence (work/TASK-065/evidence/, not published)
1280 tests, only baseline failures; 35 structure tests; golden byte-identical on 114 inputs and the 3 DGNL window files (DGNL refined3 differs only in 4 Section lines per prompt); 6/6 mutations killed.

## Limits
D7: a lone `A. TRUE` line at the start of a context is peeled as a heading (cannot be told from `A. GRAMMAR`); low: a wrapped option A is peeled the same way, and the passage-list-as-options fallback is unflagged. 65.4 (section note), 65.7 (restart-aware refs) and 65.9 (parsing accuracy metrics, REQ-0074) are not done; no paid or real-exam run.

User instructions honoured: RAW-00192.
