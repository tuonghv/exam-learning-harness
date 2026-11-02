# Report phase 50: cheap-model (Haiku) fallback for uncertain boundaries (TASK-050; REQ-0053)

Verdict: adopted at tier 0, off by default. The rules stay the primary route; only lines the rules cannot classify (first target: unfamiliar question-start words/markers such as `Bài 3:`, `Item 3)`, `Q3.`; then unknown section/subject headings and question ends) may go to Haiku, in windows of at most 40 lines. No real Haiku call was made.

## How it works
`ingest/boundary.py`: suspects -> windows -> strict-JSON prompt -> code validation (labels, indices inside the window, confidence, size, nesting) -> hints consulted by `segment` only where the rules reported uncertain. A hint never overrides a strong rule match, never becomes proof (AI-origin warnings, existing numbering and completeness gates still decide), never sets the exam Subject, and answer-key lines never reach a prompt. `--boundary-ai {off,haiku}` (default off) needs exactly one of `--mock FILE | --dry-run | --real`, else exit 2; `--max-cost-usd`, shared reply cache (`replycache.py`, reusable by the cut-detector task), `claude -p` with alias `haiku` in an isolated cwd. Estimated cost about $0.003 per window call.

## The measurement that mattered: rules before AI
The free dry-run on the real DGNL text first showed 2 windows. Investigation found real rule weaknesses behind them, fixed by rules (cost: $0):
- `3.1.`-style sub-numbers were taken as questions (11 phantom blocks, 158 -> 147 blocks). Fixed in `segment._Q`.
- Removing them left the sub-headings glued into option D (printed 30 and 102): found by a verifier reading the PDF against the renders, not by block-level checks. Fixed with `segment._is_subheading` (heading goes to the next question's context). Now 1.2 is in the context of printed 31-35, 3.2 of 103-105, 3.1 of 91-93, nothing lost, other 143 blocks byte-identical; the dry-run shows 0 windows.
- `PHẦN 1/2/3` headings no longer glued into option D; `select_pages` keeps hints; a deeply nested model reply no longer crashes the parser (RecursionError caught in the shared parser, protects refine too).

## Quality evidence (work/TASK-050/evidence)
779 tests, only the 3 known failures (identical at base), 52 boundary tests OK; cost safety with a fake `claude`: 0 invocations with the flag off, no mode, two modes, --mock, --dry-run; --real used model haiku in an isolated cwd, cap and cache honoured; 14 forged reply shapes rejected; 8 mutations killed; 0 old assertions removed; no schema/solver/config change.

## Limits
- No real Haiku accuracy is claimed (none measured); with 0 windows on the only real exam source there is nothing to ask the model yet: REQ-0053 AC5 moved to user-provided input (an exam with unfamiliar markers).
- Open low defects: DEF-6 two headings in a row (the first stays in D), DEF-7 an uppercase wrapped tail like `2.5 KM` before a question moves to its context, DEF-C `1.1` heading ends the intro block; 27 number-led non-question lines remain accepted by the rules on the DGNL text (sub-lists, values), none touching the 120 real questions.
- Vision refine route not covered (the vision call reads layout); `boundary_ai` key not added to engine.json (an old settings test would break): CLI default is off.

User instructions honoured: RAW-00147, RAW-00148, RAW-00133 (quality), RAW-00142 (short roles).
