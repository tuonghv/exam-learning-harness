# Report phase 72: the second DGNL sample exam, 2025 (TASK-072; REQ-0077)

Verdict: the pipeline ran end to end on a new exam without exam-specific code: 120 of 120 questions extracted and answered, 0 declined, for 2.33 USD (refine 0.72, four solves 1.61). No accuracy claim yet: the PDF has no answers inside and the user will supply them later (REQ-0081).

## Run
- Free layout inspection: pages 1-5 are cover and instructions, pages 6-20 the exam (120 questions, `PHẦN` headings, shared passages announced by "Dựa vào thông tin dưới đây", English blocks "Questions X-Y"); all exam pages have a text layer; Math pages 14-15 carry many embedded images.
- Refine (`--all-pages`, windows, cache): 15 calls, 120 questions numbered 1-120 with none missing; the four cut questions (52, 64, 90, 111) came out whole through the multi-page window; flagged for review: 62 and 71.
- Four exam files by question range (Vietnamese 1-30, English 31-60, Math 61-90, Science 91-120) with `Source pages` on every question; solves with the page-image check on doubtful questions (cap 0.80 USD each): Vietnamese 0.44 USD (image differs on 2), English 0.38 (9 malformed first-round replies recovered), Math 0.24, Science 0.55 (image differs on 3).
- Flags: reasons no_independent_check 101, no_review 7, solver_uncertainty_not_low 5, text/image differ 3, reviewer_disagrees 3, check_failed quote 1; no answer reached PASS. Check these first when the answers arrive: printed 1, 17, 28, 106, 107, 108, 117 (FAIL or image differs).

## Where the answers are (untracked)
`reports/dgnl2025/answers.tsv` (printed number, subject, answer, status, reason, source, uncertainty); raw outputs and prompts in `plans/dgnl2025/`.

## Limits
No answers, so accuracy is unmeasured; on the 2026 sample the same pipeline scored 92.5 percent (run 3) with every answer UNCERTAIN. Math embedded images were not individually viewed. The flag-versus-wrong separation (REQ-0079) can be measured when the answers arrive.

User instructions honoured: RAW-00198.
