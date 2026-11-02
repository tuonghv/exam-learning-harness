# Phase 54 - Clean four-level exam format
Task: TASK-054 · REQ-0057 (AC0-AC5) · Status: draft

## Goal
Exam text before any solve has four labelled levels: (1) `## Section:` (SUBJECT/PART, once per
section), (2) `### Instruction for this group` (GUIDE, in every question of its group), (3)
`## Question N` (HEADER), (4) `### Passage` (optional) + `### Question text` + options (REAL QUESTION).
Seen when: e3-English q1-5 each carry the guide, `1.2. TIẾNG ANH` appears once, not in any stem.

## Root cause (evidence)
- Heading sits in the refined/segmented `context`, not in `text`: work/dgnl-real/e3-English.md:18-19,30-31.
- refine.py:342 `split_part` strips only `PHẦN I-V` and only from `q["text"]`; context untouched.
- segment.py:152-154 puts `_PART_ANY`/`_is_subheading` lines into `pending` -> `context` (text path).
- api.py:110-121 `_share_context` repeats the whole context (heading + guide) to every group member;
  api.py:140-146 / 209 write it into each question block.

## Constraints
- Old exam files (examples/, evals/, tests fixtures) parse and prompt byte-identically (no labels = old path).
- `q["text"]` keeps its meaning for all consumers (verifier.py:190, refcheck, engine.py:63/81,
  examples_check): text = guide + passage + stem joined, minus heading and label lines.
- No refine prompt change (dev/ingest/refine.md): normalisation is deterministic post-processing at
  exam-text emission, so refined*.json and the refine/boundary reply caches stay valid (no cache key issue).
- Solver prompt cache: none (solver.solve_prompt builds per run) -> nothing stale.
- Stdlib only; no new AI call (unknown heading -> warning; REQ-0053 `--boundary-ai` stays the only opt-in AI).

## Plan modes
- Markdown/legacy exam: unaffected (no `## Section`/`###` labels) - golden diff proves it.
- Refined path (`_from_refined`) and text path (`_from_questions`): both changed via one helper.
- Solve / retry / QA prompts: solve sends the file (now labelled); retry re-renders labels; QA unchanged.

## Design
### 54.1 Format spec (owner: examples/FORMAT.md §Input)
Add after `## Instructions`, optional, documented with the 31-32 example:
```
## Section: 1.2. TIẾNG ANH            # level 1, once, before the first question of the section
## Question 1                         # level 3
### Instruction for this group        # level 2, repeated in each question of the group
Questions 31-35: Choose a suitable word or phrase (A, B, C, or D) to fill in each blank.
### Passage                           # optional, shared text of the group
### Question text                     # level 4
Jane was careful. ... _____ ...
A. read ...                           # options as today
```
Rules: nested sections joined by ` > ` on one line (`PHẦN 1: NGÔN NGỮ > 1.2. TIẾNG ANH`); a question
without `###` labels is all stem (today's form); `[Incomplete: ...]` marker stays after the stem.

### 54.2 Heading detection (owner: ingest/segment.py, new `split_heading`)
`split_heading(context: str) -> (headings: list[str], rest: str)`: peel leading lines while a line is
a heading: `_PART_ANY` match, or `_SUBHEAD` + >=60% upper letters + <=60 chars (factor the letter test
out of `_is_subheading` segment.py:36-45 into `_mostly_upper(line)`), or a bare upper line that
`router.heading_subject` maps. Stops at the first non-heading line (guide, passage). An uppercase
passage title ("THE HISTORY OF TEA") is not peeled: not PHẦN/N.M., maps to no subject.
`split_guide(rest) -> (guide, passage)`: first line(s) matching `_INTRO`/`_READ` = guide; remainder = passage.

### 54.3 Exam-text emission (owner: ingest/api.py `_share_context`, `question_lines`, `_from_refined`, `_from_questions`)
- Before `_share_context`, map each q: `headings, ctx = split_heading(q.context)`; q gets `section`
  (` > `.join, carried forward from the previous q when empty) and `context = ctx`. So `GROUP_RE`
  (api.py:115) now sees the guide only; the heading never enters the shared context.
- Emit `## Section: <section>` when the section changes (before `## Question k`).
- `question_lines(q)` (api.py:140): when context has a guide, emit `### Instruction for this group`,
  guide, optional `### Passage`, then `### Question text`, stem, figures. No context -> today's lines.
- `_from_questions` (api.py:209) uses `question_lines` instead of its inline copy (reuse, one writer).
- refine.py:342 unchanged (part letter still recorded); refined.json unchanged.

### 54.4 Parser (owner: pipeline/parser.py `parse_exam`)
- `## Section: X` -> `cur_section = X`; appended to `res["sections"]` (list[str]); not a question.
- Question body split on exactly-`###` lines (reuse `sections(body, 3)`); new q keys `section`,
  `instruction`, `passage`, `stem`; `text` = non-empty of instruction, passage, stem joined by `\n\n`
  (unlabelled body: stem = text = today's value). Options parsed from the whole body as today.
- `res["section_subjects"]` = {section: router.heading_subject(section)}.

### 54.5 Heading -> subject (owner: pipeline/router.py, new `heading_subject(heading) -> key|None`)
Take the last ` > ` segment that maps; per segment strip `^(PH[ẦA]N|PART)\s+\S+\s*[:.\-–]?\s*` and
`^\d+(\.\d+)*\.?\s*`, then `subject_key` (fold = diacritic/case-insensitive, utils/text.py:5).
Aliases come from config/subjects.json (`tiếng anh`, `tiếng việt`, `toán`, `khoa học` already present;
add none unless a test fails). `validate_exam` adds warnings (not errors), printed `WARN:` by engine:
`section_subject_unknown: <heading>`; `section_subject_mismatch: <heading> -> <key> vs Subject <x>`.
Mixed file: subject prompt is per section file (DGNL e3-*.md already per subject); a mismatch warns.

### 54.6 Labelled solve/retry prompt (owner: pipeline/solver.py `render_questions`)
- `solve_prompt` unchanged: it sends the labelled file (54.3), so blocks reach the solver as written.
- `render_questions` (solver.py:55, retry): per q emit `## Section:` on change, `## Question N`,
  `### Instruction for this group` + instruction, `### Passage`, `### Question text` + stem, options;
  unlabelled q -> today's output byte-identical. Answer/decline logic untouched.

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| Passage title peeled as heading | not peeled unless PHẦN/N.M./subject alias | golden diff shows passage intact |
| Unknown heading (`TƯ DUY ĐỊNH LƯỢNG`) | kept as `## Section:`, warning | `WARN: section_subject_unknown` |
| Section subject != header Subject | warning, run continues | `WARN: section_subject_mismatch` |
| Heading with no guide/passage | context empty, Section line only | stem block only |
| Old exam file | no labels -> old parse/prompt | golden byte-equal |

## Unit tests (tests first; fixtures = 2-page slices built inline, no copyrighted text beyond the user's pasted 31-32)
- test_ingest_core: `split_heading` cases: `1.2. TIẾNG ANH`, `PHẦN 1: NGÔN NGỮ\n1.1. TIẾNG VIỆT`,
  `PHẦN II`, bare `TOÁN`; uppercase passage title not peeled; guide line not peeled.
- test_ingest_refine (refined slice q31-35 of a 2-page doc, context `1.2. TIẾNG ANH\nQuestions 31-35: ...`):
  output has exactly one `## Section: 1.2. TIẾNG ANH`; each of 5 question blocks has the guide once under
  `### Instruction for this group`; `TIẾNG ANH` absent from every question block (AC1, AC2).
- text path slice (segment + `_from_questions`): same assertions.
- parser: labelled file -> sections, q.section/instruction/stem; `text` = guide+stem (no heading);
  unlabelled examples/english/input-001.md -> same dict as before plus empty new keys.
- test_router: `heading_subject` for the 4 headings + `tieng anh` (no diacritics) + unknown -> None;
  validate_exam warnings unknown/mismatch.
- solver: `render_questions` golden for labelled q; unlabelled byte-identical; `solve_prompt` for the
  31-35 slice contains `Instruction for this group` 5x and the heading 1x (AC5).
- Regression golden: render every input under examples/, evals/inputs/ -> parse dict and solve_prompt
  unchanged.

## Verification
| Item | command -> expected | tier |
|---|---|---|
| 54.1-54.6 | `python3 -I -m unittest discover -s tests/unit` -> OK, 0 failures | 0 |
| AC3 DGNL | re-emit e3-*.md from work/dgnl-real/refined3.json (existing ingest cmd, no AI); per subject: question count 30, option dicts equal to old e3-*.md; diff = heading lines moved to one `## Section`, guide/passage/stem under labels only | 0 |
| AC5 golden | `exam.py` prompt print (cli.py:86) on new e3-English.md -> `Instruction for this group` once per q1-5, `1.2. TIẾNG ANH` once | 0 |
| answers unchanged | optional paid re-solve of English q1-5 only (main decides) | paid |

## Decisions
- Normalise at emission (api.py), not in refine or the refine prompt - no re-refine, caches valid.
- Labels as `##`/`###` Markdown headings - parser already splits on heading levels; `without_questions`
  (engine.py:69, splits on `^## `) keeps `## Section` chunks and drops only question chunks.
- Keep `q["text"]` as the joined content - QA/verifier/refcheck untouched. Rejected: re-render the
  whole exam from parsed parts in solve_prompt (changes every prompt, larger regression).
- Per-question subject prompt in one mixed file: rejected; per-section files + mismatch warning.

## Risks
- `_share_context` behaviour change for contexts that began with a heading and no group line (heading-only
  context was shared nowhere; now dropped to Section) - covered by text-path test.
- `### ` inside an old stem (unlikely) would now split; regression golden over examples/evals detects it.

## Out of scope
New AI subject classifier; per-question subject prompts in one file; review-pack header changes (phase-52 already shows subject once).

## Defects
- D1 (major) api.py:110-121 + refine.py:342: section heading `1.2. TIẾNG ANH` repeated in every question
  context of a group; evidence work/dgnl-real/e3-English.md:18,30,42.
- D2 (minor) refine.py:121 `PART_RE` only Roman `PHẦN I-V`; `PHẦN 1` / `N.M. TITLE` never stripped (segment.py:16-18 notes the asymmetry).

## Follow-up
REQ-0058 (group-aware solving: independent / passage / dependent) builds on the guide and passage levels from 54.3-54.4; designed after this task.
