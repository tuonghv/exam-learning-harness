# Phase 55 - Group-aware solving
Task: TASK-055 (REQ-0058, RAW-00168, note tmp/solve-strategy-context.md) · Status: draft
Builds on phase-54 (54.3 emission, 54.4 parser, 54.6 render_questions). Smallest change, no rewrite.

## Goal
Each question reaches the model with exactly the context it needs: independent = own block (+ group
guide); passage/table/chart group = shared context once per call; dependent = its siblings. Seen when:
a `--questions` slice that starts mid-group still carries the passage; a retry of 1 of 7 passage
questions carries the passage once; a reference to an absent question/passage declines `missing_text`.

## 1. Current flow (map)
ingest (refine.py:316-366 per page, carries context across a page break :340; `page` per question :361)
-> api.refined_questions (merge page-cut question :126) -> [`--questions` filter :171-173]
-> _share_context (copy group context by `Questions 46-52` range :110-123) -> question_lines (four
levels; figure = `[Figure/table: desc]` text line :154) -> renumber 1..n, printed offset line :180-182
-> exam.md. solve: parser.parse_exam (:58-100, q.text = ins+passage+stem) -> engine.run (:122):
incomplete markers skipped (:142) -> round 1 = ONE call with the whole file (solver.solve_prompt :49)
-> det_checks -> QA = one call, per-question q.text (verifier.qa_prompt :184) -> retry = one call
with only the open ids (solver.retry_prompt :73, render_questions :55). Images: only cross-solve route B
(cross.py:17-42), never in `solve`.
What works: round 1 sees every passage and every sibling (whole file); labelled q.text keeps the
passage for QA/retry; refcheck declines paragraph/figure refs with no content (refcheck.py:34-44).

## Gaps
- G1 (high) api.py:171-177 `--questions` filter runs BEFORE `_share_context`: slice 48-52 of group 46-52 drops q46 (the only carrier of guide+passage) -> 48-52 solved without the passage, no decline. = Defect D1.
- G2 (high) retry/QA drop sibling answers: retry_prompt renders only open ids (solver.py:86), qa_prompt only `ids` (verifier.py:188); a stem "dùng kết quả câu 3"/"using your answer to question 3" loses q3 on retry/QA.
- G3 (med) labelled emission repeats the passage in every member (api.py:146-150 via _share_context copy) -> round 1 prompt carries a 7-question passage 7 times (cost, and the model may treat copies as different texts).
- G4 (med) GROUP_RE (segment.py:7) misses `từ câu 1 đến câu 5`, `câu 1 đến câu 5`, `Câu 3, 4`, `Questions 1 and 2` -> VN reading / math shared-data groups are not shared on members.
- G5 (med) no "passage expected but absent" check: instruction says "Read the passage"/"Đọc đoạn trích" and `### Passage` empty -> solved blind (refcheck only knows paragraph numbers and figures).
- G6 (med) visuals are text-only in `solve`: a chart/diagram question gets `[Figure/table: desc]`; when desc is thin the model guesses. Page images exist only in cross-solve.
- G7 (low) traceability: question `page`/`continued_pages` (refine.py:361, api.py:132) are not written to exam.md, so result.json cannot point to source pages.
- G8 (low) dependency refs use printed numbers while exam ids are renumbered (api.py:180-182); a "question 47" ref must map via the offset.
- G9 (low) round 1 is all-or-nothing: one malformed reply fails every question (solver.py:102-108). Acceptable today (retry), noted for alternative B.

## Constraints
- Old files (examples/, evals/, unlabelled) keep byte-identical solve/retry/QA prompts (golden).
- q.text meaning unchanged (verifier, refcheck, examples_check). Stdlib only; no new AI call by default.
- Caches: solver/QA have no reply cache (phase-54 Constraints); refine cache untouched (emission-only change). Prompt template edits go to prompts/dev + release bump (prompt_info in result.json).
- Call caps unchanged: call_cap = 1 + 2*max_attempts (engine.py:20) still holds (same call count).

## Plan modes
- Markdown/legacy: unaffected (no labels -> no groups). Refined + text path: 55.1, 55.2, 55.6. Solve: 55.3-55.5. cross-solve: unaffected.

## Design
### 55.1 Slice after sharing (owner: ingest/api.py `_from_refined`)
Call `_share_context(qs)` on all refined questions, then apply the `spec` filter. Fixes G1.
### 55.2 Group range forms (owner: ingest/segment.py `GROUP_RE`)
Also match `(từ )?câu N (đến|-) (câu )?M`, `Questions N and M`, `Câu N, M(, K)` (list -> min..max). Fixes G4. Keep `refine.PART_RE` sync note.
### 55.3 Group model (owner: pipeline/parser.py, new `groups(exam) -> [{"key","kind","ids","instruction","passage"}]`)
Pure, derived, no new file syntax: consecutive questions with equal (section, instruction, passage) and
non-empty instruction or passage = one group. kind:
- `independent`: no passage, and no sibling ref (guide-only group: guide is the only shared part).
- `passage`: non-empty passage (text, table rows `|...|` or `[Figure/table:` lines count as passage).
- `dependent`: any member stem refs another question (`câu N`, `question N`, `ý (a|b)`, `kết quả (câu|ý) trên`, `previous (question|answer)`), N mapped printed->id by the offset line (G8). A dependent ref also adds the referenced id to the group even across groups (`deps: {id: [ids]}`).
### 55.4 Group-aware render (owner: solver.py `render_questions`, `retry_prompt`; verifier.py `qa_prompt`)
- Labelled files only (old path untouched): emit per group `## Group <first>-<last>` + instruction +
  passage ONCE, then each `## Question N` with `### Question text` + options (G3). Round 1 for labelled
  files = render of all ids (replaces raw file text; parsed content only, same words).
- Retry ids closure: open id i -> its group context once; for `dependent`, sibling stems + their current
  answers under `### Sibling answers (context, do not re-answer)`; ids in a cycle are all open together or
  the closed ones are given as context, so no ordering is needed (one call; cycles harmless).
- QA: same context block per group; dependent items get `sibling_answers` field.
### 55.5 Missing-context decline (owner: core/refcheck.py, new `missing_group_parts(exam, groups) -> {id: [reasons]}`; engine.py:142)
- dep ref to an id not in the file (slice cut) -> `solver_declined: missing_text (question N)`.
- instruction asks for a passage/text/table (`Read the (following )?(passage|text)`, `Đọc (đoạn|bài|văn bản)`, `bảng số liệu sau`, `use the following data`, `dữ kiện sau`) and passage empty -> `missing_text (passage)`.
Uncertain link (group range not covering the question, or a ref word without a number such as "the text"): never decline, never guess a link -> `WARN: group_link_uncertain: q N` (exam_warnings) and solve with what the file holds; reviewer sees the warning in run output.
### 55.6 Source pages (owner: api.py `question_lines`; parser.py)
Emit `Source pages: 3-4` as the first body line of each question (from page + continued_pages); parser strips it into q["pages"] (not in q.text); build_result adds `"pages"` per question (schema RESULT optional field). Fixes G7; enables 55.7.
### 55.7 Visual attach (optional, stage 2, owner: engine.run + adapters claude.run_claude_images, refine.render_page)
Behind `solve --pdf FILE`: groups whose context holds `[Figure/table:` get their source pages as PNG in
that call. Needs a split call shape for those groups only (= alternative B for visual groups). Recommend a
separate task after 55.1-55.6 show real visual misses (G6); not needed for the text fixes.

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| slice starts mid-group | context shared before filter (55.1) | passage in each sliced question |
| passage expected, absent | decline missing_text (passage) | UNCERTAIN, reason names passage |
| ref to question outside file | decline missing_text (question N) | UNCERTAIN |
| dependency cycle 3<->4 | both in one call / closed one as context | normal statuses |
| uncertain link | solve, no link guessed | WARN group_link_uncertain |
| malformed reply round 1 | unchanged (all UNCERTAIN, retry) | malformed_output |
| unlabelled/old file | old path | byte-identical prompt |

## Unit tests (tests first; inline 2-page slice fixtures, stdlib unittest, mock llm)
1. 55.1: refined doc p1 = q46 guide+passage, p2 = q47-52; `--questions 48-52` -> each block has the passage.
2. 55.2: GROUP_RE matches the 4 new forms; `Câu 3, 4` -> (3,4); old forms unchanged (table test).
3. 55.3: fixture with independent MCQ q1, passage group q2-4 across pages, table q5, dependent q6->q5: kinds and deps exact.
4. 55.4a: labelled round-1 prompt holds the passage exactly once per group (count == 1).
5. 55.4b: retry of q3 only -> passage once, q2/q4 absent; retry of q6 -> q5 stem + answer under Sibling answers.
6. 55.4c: cycle q7<->q8, q7 PASS, q8 FAIL -> retry has q8 open, q7 as context; no recursion error.
7. 55.5: dep ref to q99 -> declined missing_text (question 99), no call for it; "Read the passage" + empty passage -> declined (passage); ref "the text" without guide -> warning only.
8. 55.6: `Source pages: 1-2` parsed to pages [1,2], absent from q.text; result.json carries pages.
9. Golden: every examples/ and evals/ input -> solve/retry/QA prompt bytes unchanged.

## Verification
| Item | command -> expected | tier |
|---|---|---|
| 55.1-55.6 units | `python3 -I -m unittest discover -s tests/unit` -> OK | free |
| golden | same suite, golden test -> 0 diff | free |
| 55.4 real prompt | `exam.py solve <2-page slice>.md --dry-run` -> passage count 1 per group (grep -c) | free |
| end-to-end | `exam.py solve <slice>.md --mock <replies>.json` -> statuses as unit 7 | free |
| accuracy | one real run on a DGNL English + VN reading slice (main decides, paid) -> no missing-passage answers | paid, optional |

## Decisions (alternatives compared)
- A (chosen): keep one whole-file call in round 1; add derived groups, group-aware render/retry/QA, slice fix, decline rules, page trace. Cost: same call count, smaller prompts (G3); accuracy: fixes the real losses (G1, G2, G4, G5); risk: low, old path byte-identical.
- B (rejected now): one call per group (independents batched by K). Isolates malformed replies (G9), smaller calls, enables images per group; but N calls instead of 1, system prompt repeated (cost x groups), call_cap/Runner logic changes, loses cross-group view. Justified only when run.log `prompt_bytes`/answer limits are hit or for 55.7 visual groups.
- C (rejected): per-question calls with context. Highest cost, no accuracy gain over A for MCQ.
- D (sophisticated, rejected now): dependency DAG with topological order, forward-passed accepted answers, figure crops, AI link classifier for uncertain links. More moving parts and paid calls; A covers cycles by solving together; revisit if dependent-question failures persist after A.
- Uncertain links: warn, never guess (a wrong link is worse than none); decline only on explicit evidence.

## Out of scope
New file syntax for groups; AI group classifier; image solving in `solve` (55.7 = separate task); prompt rule rewrite beyond one line in solve.md ("a `## Group` block is shared context of its questions").

## Risks
- Labelled round 1 now renders from parse, not raw file: a parse loss would hide text -> golden on phase-54 labelled fixtures + content-equality test (all words of file in prompt).
- Dependency regex false positives (`câu 3` inside a passage) -> scan stems only, not passage.

## Defects
- D1 (major) src/exam_engine/ingest/api.py:171-177: `spec` filter before `_share_context`; questions of a group whose carrier is outside the slice lose guide+passage silently. Evidence: code order lines 171-173 vs 177; `_share_context` range state built only from present questions (:117-121).
- D2 (minor) src/exam_engine/ingest/segment.py:7 GROUP_RE: no match for `từ câu 1 đến câu 5` / `Câu 3, 4` (regex requires a digit right after `đến`).
- D3 (minor) src/exam_engine/pipeline/solver.py:73-86 and verifier.py:184-199: sibling answers never passed for dependent stems on retry/QA.
