# Phase 53: senior-solver QA merged into the review pack (TASK-053; REQ-0056)
Goal: the user reviews extraction; answer correctness is the QA's job. Reuse: review.py (TASK-052), the QA tables the independent-read subagents already produce (work/TASK-039/handoff/indep-*.md and adjud-*.md: tables `n | answer | conf | note` and `n | answer | conf | flawed? | reason`, printed numbers).

## QA file format (one per subject, input only)
`n | answer | conf | flawed | reasoning` pipe table (header row allowed, extra columns tolerated, `-` for no answer, `flawed` yes/no/mild). Adjudication rows override independent-read rows for the same printed number (the merge is done by the tool: `--qa FILE [--qa FILE2]`, later files win).

## review-pack changes
`review-pack ... --qa FILE [--qa FILE]` fills the `QA:` line of each section: `QA: <letter|-> conf <..> | <verdict> | <reasoning 1-3 lines>`, verdict computed by the tool: `agrees` (QA letter == engine letter), `differs` (both letters, not equal), `flawed` (QA marks the question flawed or mild flawed), `qa-only` (engine declined, QA answered), `unresolved` (QA `-`); INDEX.md gets two columns `qa` and `verdict` and a summary per subject (agrees/differs/flawed/qa-only/unresolved counts). Without `--qa` the line stays `QA: -` and old behaviour is unchanged. QA rows for printed numbers outside the subject are reported as `qa_unmatched` (count, numbers).
Marks the user typed are preserved on re-run (TASK-052 rule).

## Merge script (main, not engine code)
For the DGNL sample: a small script under work/TASK-053/ turns the existing handoffs into four QA files (Vietnamese from indep-vietnamese + adjud-vietnamese, English from indep-english, Math from indep-math, Science from indep-science + adjud-science), plus rows for printed 10, 23, 66 from the TASK-040 real run (answers B, B, A, which equal the independent reads; independent reads already contain them). Notes: sources are in-session independent reads of the PDF (same model family: say so in the pack header; agreement is not a key).

## Skill solve-qa (main writes)
Short: how to run the QA pass without API cost (independent read per section from the source, never the engine output; adjudicate disagreements and low-confidence items with a second independent read; flawed-question flag; printed numbers only; small slices; unresolved stays unresolved).

## Tests-first list (tier 0, synthetic)
1. `--qa` with a table fills QA lines and verdicts for agrees/differs/flawed/qa-only/unresolved; INDEX has the new columns and counts.
2. later `--qa` file overrides earlier for the same number; extra columns and header row tolerated; malformed rows reported as `qa_unparsed`, nothing guessed.
3. QA numbers outside the subject -> `qa_unmatched`.
4. without `--qa` output byte-identical to TASK-052; user marks preserved on re-run with a new QA file.
5. real smoke: DGNL four subjects with the generated QA files; counts: agrees/differs/flawed/qa-only/unresolved per subject printed; known cases: 8 agrees? (engine A, adjudicated A), 112 differs, 120 (engine A, QA A low flawed), 10, 23, 66 qa-only.
## Plan modes
Reads QA files only; no model call; no change to solve/result files.
## Verification
Tier 0 tests + real smoke; the tester recomputes the verdict table from the QA files and result.json with its own script.
## Risks
Same-family QA is not an official key (header says so); QA table mistakes (wrong number offset): printed numbers only.
