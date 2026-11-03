# Phase 65 - Exam structure and scoped context (TASK-065)
Task: TASK-065 · REQ-0073 (RAW-00192, brief tmp/Exam-Structure-Context.md) · Status: designed
Probe: work/TASK-065/probe/probe.py -> out.jsonl (12 synthetic cases through the real `api._from_refined` + `parse_exam` + `groups/deps` + `refcheck`).

## Goal
Every question reaches the solver with the instructions and shared material that apply to it, and none
from another section; structure doubts are flagged, not guessed. Seen when: probe cases P1-P4, P7, P10, P11
give the expected rows (65.x Unit tests) and DGNL re-emission keeps its 120 questions, options and groups.

## A. Current architecture (keep all of it)
ingest refine (context per q, passage carried over page breaks refine.py:530-542) -> api.refined_questions
(page-cut merge :126) -> `_share_context` (heading peel + range copy :110-123) -> `question_lines` four
levels + `Source pages` (:142-158) -> exam.md -> parser.parse_exam (Section / Instruction / Passage / stem
:86-129) -> groups()/deps() (:264-315) -> render_questions (group context once, solver.py:77-106), QA,
refcheck.missing_group_parts declines, exam_warnings, assembly provenance rows (api.py:227), metrics.
Representation is already a hierarchy-lite: Section path + group + question. Inheritance today = copy the
range context into each member at emission, dedup at render. That model is right; its scope rules are not.

## B. Gap analysis (C = confirmed by probe run, P = potential, code-read only)
| Gap | Evidence | Impact | Root cause | Prio |
|---|---|---|---|---|
| G1 range leaks into next section after numbering restart | C P1: part II q5-6 get part I instruction | wrong instruction, wrong answers | emission: api.py:117-121 range state not reset on section change | high |
| G2 question-own context inside a range is dropped | C P2: q3 "antonym" line gone from file | silent text loss | emission: api.py:120-121 replaces ctx | high |
| G3 heading/passage line `A. ...`/`B. ...` taken as option | C P10b: validate error "options must be exactly A-D"; C P11: passage emptied -> both q declined missing_text | exam rejected / false declines | parser.py:104-107 scans whole body for options | high |
| G4 lettered/Roman headings (`I. X`, `B. Y`) not sections | C P10: `I. READING` repeated in every stem, no Section line | tokens, structure lost | segment.py:67-79 knows only PART/N.M/subject | med |
| G5 section instruction without a range reaches q1 only | C P3 | later questions lose instruction | emission: no scope for unranged guide | med |
| G6 reference after restart maps to the wrong question | C P7: deps {4:[1]} = part I q1, not part II q1 | wrong sibling context | refined path writes no printed map (api.py:190); deps uses offset only (parser.py:267) | med |
| G7 lower-case range word not seen | C P4: "answer questions 5-7" -> q6-7 without passage, no flag | solved blind | segment.py:22 GROUP_RE case-sensitive group word | med |
| G8 shared table without range: no link, no flag | C P6: q2 "table above" incomplete=0 | retry/QA without table | no range; refcheck _FIG did not fire | low |
| G9 section path loses parent (`1.2.` alone replaces `PHẦN 1 > 1.1.`) | P api.py:115 vs FORMAT.md:50 example | traceability | flat `sec` | low |
| G10 second instruction line filed as passage | C P5 (text kept, label wrong) | low | split_guide first line only (segment.py:98) | low |
Works (C): range share incl. instruction after passage when capitalised (P4b), cross-page merge + `Source pages 3-4` (P8), passage once per group, missing-passage decline.
Real-run weight: TASK-060 failures.md has passage_link 0 of 42; DGNL (refined3.json) contexts are all first-line ranges, no restart, no lettered headings. So G1-G7 are latent for DGNL and real for other exam kinds; no accuracy gain expected on DGNL, the gain is generality + no silent loss.

## Constraints
- DGNL refined3 re-emission and examples/, evals/ inputs: parse dict, solve/retry/QA prompts unchanged except G9 Section lines (expected diff, named golden update).
- q["text"] meaning unchanged (verifier, refcheck, examples_check). Stdlib only; no new AI call, agent or file format.
- Caches: all changes are emission/parse/render; refine and boundary reply caches keyed on refine input stay valid. Solver/QA have no reply cache. solve.md one-line edit -> prompts/dev + release bump.

## Generality
All exam kinds with sections and numbered questions; heading forms by shape (roman/letter/arabic + mostly upper), group words via langtable (re.I), no exam/subject literal; synthetic non-DGNL fixtures = probe cases.

## Known incidents
none (failures.md cause table: passage_link 0).

## C. Alternatives
| Option | Complexity | Benefit | Limits | Fit |
|---|---|---|---|---|
| A validation flags only | low | operator sees G1-G8 | answers still wrong/lost | full |
| B (chosen) fix scope rules in emission + parser, section note level, flags, structure score | low-med, 5 files | fixes all confirmed gaps, no new format | heuristic section-note scope | full, old files byte-identical |
| C node tree IR (SECTION/INSTRUCTION/PASSAGE/QUESTION ids, per-question snapshots) | high | explicit parents/refs | new format, every consumer, snapshot tokens N x | poor |
| D Claude-assisted structure read for doubts (like --boundary-ai) | med + paid | handles odd layouts | cost, no evidence of need | later, only if 65.8 flags > 5% on a real run |

## D. Recommended solution (B)
Inheritance resolved at emission for scope (deterministic facts: section, range, own ctx), stored once per
scope node in the existing Markdown, and rendered once per call (question preparation). Tokens: no per-question
snapshot; a section note costs its length once per call, group context once per group (55.4). Precedence by
proximity: Section note < group instruction < question-own line (first line of Question text); solve.md says so.

## Plan modes
Markdown/legacy files and unlabelled exams: unaffected except the intended Section-line change. Refined four-level path (ingest -> solve): 65.1-65.8. Cross-solve: unaffected.

## Design
### 65.1 Section-scoped ranges (owner: api._share_context)
Reset `cur` when `sec` changes; a range never covers a question of another section. Fixes G1.
### 65.2 Question-own override (owner: api._share_context)
In range and own ctx non-empty, not a range line: context = group ctx; own ctx prefixed to `text` (Question
text level), flag `instruction_override`. Fixes G2.
### 65.3 Range word case (owner: segment.py)
`GROUP_ANY = re.compile(GROUP_RE.pattern, re.I)` used only by `_share_context`; GROUP_RE (segmentation, option D split) unchanged. Fixes G7.
### 65.4 Section note (owner: api._share_context/_from_refined/_from_questions; parser.parse_exam; solver.render_questions/_render_plain; verifier.qa_prompt)
- Emission: heads non-empty, rest has no range, rest <= 2 lines and <= 300 chars, no table/figure line -> rest
  becomes the note of that section, written as body of `## Section: X`; flag `section_instruction_inferred`.
  Else today (stays with that question).
- Parser: body of a Section chunk -> `res["section_notes"][X]`; `## Section:` chunk without body -> no key (old dict).
- Render: after each emitted `## Section:` line, the note (once per call). Scope ends at the next Section line.
- FORMAT.md: one line "A `## Section:` body is the instruction of the whole section." solve.md rule 5 adds "a `## Section` body applies to every question below it until the next Section; nearer text overrides it". Fixes G5.
### 65.5 Enumerated headings + section stack (owner: segment._is_heading_line, split_heading; api._share_context)
- Heading also: `^(?:[IVXLC]{1,4}|[A-Z]|\d{1,2})[.)]\s+\S`, <= 60 chars, `_mostly_upper` (peeled only from the start of a context, so options are not touched).
- `kind(line)` in {part, roman, letter, arabic depth n, subject}; section path = stack: a new heading pops entries down to and including the last of its kind, then pushes. Joined by ` > ` (FORMAT.md form). Fixes G4, G9.
### 65.6 Labelled option scan (owner: parser.parse_exam)
Labelled body: option lines only from the `### Question text` part; instruction/passage lines kept verbatim. Unlabelled: unchanged. Fixes G3 for labelled files; 65.5 removes the heading lines from unlabelled bodies (P10b).
### 65.7 Restart-aware refs (owner: api._from_refined; parser.deps)
Refined path: when ids restart (id <= previous), write the existing text-path line `printed numbers: k=sR.n, ...` (api.py:268 form) instead of the offset line. deps: with that map, `question N` in a stem of run R -> id of sR.N; N absent in R -> WARN `group_link_uncertain: q k`, no dep. Fixes G6.
### 65.8 Structure flags (owner: api._share_context collects; api.assembly rows `structure` list, key only when non-empty; ingest prints `WARN:`)
Codes: `range_cut_by_section` (65.1), `instruction_override` (65.2), `section_instruction_inferred` (65.4),
`range_overrun` (range end beyond the section's last question; also = instruction without questions), `shared_ref_unlinked` (stem names a table/figure/passage word, no figure/passage in its group, G8).
Existing checks kept (no duplicate): empty/duplicate/numbering (validate_exam), missing passage/question (missing_group_parts), cut/orphan/merge (UNCERTAIN, api.py:224), section subject (exam_warnings). Flags never decline.
### 65.9 Parsing accuracy apart from solving (owner: metrics.py new pure `structure_scores(exam, gold)`; metrics.compute optional `structure=` arg)
- gold JSON per fixture: `[{"id","section","instruction","group","pages","deps"}]`; scores = question count/boundary (stem prefix), section, instruction inheritance, shared-ref (group ids), cross-page (pages), deps; each a rate.
- compute(structure={id: [codes]}): rows get `parse_flag`; `by_parse_flag` slice and `counts["structure_flags"]`, keys only when given (old metrics byte-identical). A wrong answer on a flagged question is reported as parse-suspect, not solver. Avg input tokens/question = existing `_log_cost` bytes / n.

## E. Implementation plan
1. Minimum (confirmed, high): 65.1, 65.2, 65.6, 65.8 codes for them. api.py, parser.py. Risk: DGNL golden (no restart/override there -> 0 diff expected).
2. Evidence-backed (confirmed, med): 65.3, 65.5, 65.7, 65.4. segment.py, api.py, parser.py, solver.py, verifier.py, solve.md, FORMAT.md. Risk: heading peel of a passage title `I. INTRODUCTION` (mostly upper) -> golden + unit; G9 changes DGNL Section lines.
3. Measurement: 65.9 + gold for the probe cases; a DGNL gold only if main/user wants a hand-checked file.
4. Optional, only if a real run shows >5% questions flagged: alternative D for flagged questions.

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| passage title peeled as heading | stays if not enumerated+upper | golden diff |
| short q1 lead-in taken as section note | note shown once to the section | WARN section_instruction_inferred |
| range past section end | range cut | WARN range_overrun / range_cut_by_section |
| ref number absent in its part | no dep | WARN group_link_uncertain |
| old/unlabelled file | old path | byte-identical prompts |

## Unit tests (tier 0, synthetic, mock LLM; probe cases become tests)
P1: q5-6 instruction empty, no part I text; flag range_cut_by_section. P2: q3 stem holds own line, ins = group. P3: section_notes[PART I] set, render of q2-3 has it once. P4: q5-7 one passage group. P7: deps {4:[3]}. P10: section `I. READING > B. VOCABULARY`, stems clean. P10b: no validate error. P11: passage kept, no decline. Stack: `I>A`, then `B` -> `I > B`; then `II` -> `II`. 65.9: scores 1.0 on gold, one wrong section -> section rate < 1. Golden: examples/, evals/ inputs and DGNL refined3 emission unchanged except Section lines.

## G. Verification / acceptance
| Item | command -> expected | tier |
|---|---|---|
| 65.1-65.9 | `python3 -I -m unittest discover -s tests/unit` -> OK | 0 |
| probe | `python3 -I work/TASK-065/probe/probe.py` -> rows as Unit tests (P8, P4b unchanged) | 0 |
| DGNL | re-emit from work/dgnl-real/refined3.json: 120 q, options and groups() equal to before; diff = Section lines only | 0 |
| parse vs solve | metrics on a saved run with `structure=` -> by_parse_flag present; without -> metrics.json byte-equal | 0 |
| accuracy | optional paid re-solve of a restart/lettered non-DGNL exam (main decides) | paid |

## Decisions
- Resolve scope at emission, render once per call; rejected per-question snapshots (N x tokens) and parse-time copying of section notes.
- Extend `## Section:` with a body instead of a new `### Instruction for this section` label: parser already splits it, `without_questions` keeps it.
- Never guess uncertain links/scopes: flag; decline only on explicit evidence (55.5 rule kept).
- D-coordinator-1 (RAW-00192) Order: stage 1 = 65.1, 65.2, 65.6 and their 65.8 flags (confirmed major defects P1, P2, P10b/P11: instruction carry-over across a restart, deleted own override, A./B. lines read as options). Later stages only if the probe cases and metrics justify them.
- D-coordinator-2 Honest expectation: no DGNL accuracy gain (0 of 42 failures were passage links; DGNL uses first-line ranges without numbering restart); the gain is for other exam kinds and for stopping silent text loss. The Section-line change in DGNL output needs a named golden update.
## Out of scope
New IR/parser, AI structure classifier (D), multi-line instruction split (G10), refine prompt change.

## Defects
- D1 major api.py:117-121 range context leaks across sections on restart (probe P1).
- D2 major api.py:120-121 question-own context inside a range dropped from the file (P2).
- D3 major parser.py:104-107 `A.`-`D.` lines in heading/passage become options: validate error (P10b), passage emptied -> false missing_text declines (P11).
- D4 minor segment.py:22 GROUP_RE case-sensitive group word; `questions 5-7` not shared (P4).
- D5 minor api.py:190 + parser.py:267 refined path has no printed map on restart; dep mis-linked (P7).
- D6 minor api.py:115 section path drops parent vs FORMAT.md:50 (code-read).

Nova
