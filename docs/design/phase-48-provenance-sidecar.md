# Phase 48 - Provenance sidecar and prompt lines
# Phase 48 - provenance sidecar (draft for docs/design/phase-48-provenance-sidecar.md)
Task: TASK-048 · REQ-0052 (AC1-AC4) · Supersedes: phase-43 §43.6-43.7 · Status: draft

## Premise (facts at HEAD a19f328; what exists since phase 43 was written)
- Source pages: api.py:142-150 `question_lines` emits `Source pages: N[-M]` ONLY for four-level (guide) questions with `q.page`; parser.py:58-62 strips it into q["pages"]; result.json carries `pages` (55.6). Text path (segmented `doc.questions`) has no page per question (no `page` key in segment.py / pdf.py questions).
- Refined join: api.py:126-139 `refined_questions` merges same-id parts, keeps union of continued_pages, last part's `cut`.
- Completeness: refcheck.py:106-131 `incomplete_reasons` (options_incomplete, cut_unresolved, referenced_part_missing X, orphan_on_page N, unreadable, formula_unbalanced, trailing_operator, merge_suspect); :134 `incomplete_by_question`; :145 `marker` -> `[Incomplete: missing_text ...]` written by api.py:194-195 / :232-233.
- Decline: engine.py:281-283 `incomplete_ids` marks marked questions UNCERTAIN `solver_declined: missing_text (...)` before any call; parser.py:211 and review.py:93 skip them. So the deterministic gate already declines; the prompt line only covers what the gate misses.
- Refine trace (TASK-047): refine.py:278 rows {page, pages, png_sha256}, written as `<out>.trace.json` (cli.py:712-713). Page reply cache key = model + sha256(prompt) + image shas (refine.py:277) -> a refine.md edit invalidates cached pages (correct, see Risks).
- Plans: planrun.py:96 copies the exam to `plans/<exam-id>/<run>/input/exam.md`; import_dir planrun.py:277-280 same; `ingest/` holds traces (:283-288).
- validate_exam (parser.py:181) = fatal errors; exam_warnings (parser.py:216) = section/group warnings; neither is per-question completeness.
- Prompts: refine.md is read from dev ALWAYS (refine.py:33 `PROMPT_REL = dev/ingest/refine.md`); releases hold no ingest/. Solve default = config/engine.json `prompt_channel: release, prompt_release: v1.0.0`; dev system.md reaches only `--channel dev` runs. vi solves read lang/vi/system.md.
- Releases: `exam.py prompts release V` (prompts.py:41) freezes dev into releases/V, never overwrites.

## What the sidecar still adds
One machine-readable row per exam-file question linking position -> printed number -> pages -> statuses, for ALL questions (not only guide ones), in a file next to the exam, with result.json and every schema unchanged.

## Plan modes
- refined (ingest --refined): full rows, pages from page+continued_pages.
- text path (segmented PDF/DOCX/image OCR): rows with `source_pages: []` (no per-question page data; G1).
- Markdown exam-format source (returned unchanged, api.py:81-86): no sidecar written; byte-identical as today.
- solve / plan run: reads nothing new; plan run copies the sidecar if present.
- cross-solve, benchmark, genexam: unaffected.

## Design
### 60.1 `api.assembly(doc, config=None) -> list[dict]` (owner: src/exam_engine/ingest/api.py)
- Extract the shared selection from `_from_refined` (:174-189) and `_from_questions` (:215-227) into `_selected(doc, config) -> (qs, why)`; both renderers and `assembly` call it, so the sidecar can never disagree with the marker lines. Render output stays byte-identical (golden).
- Row shape (keys in this order, json `ensure_ascii=False, indent=2`):
  `{"id": "<k>", "printed": "<q.id | q.n>", "source_pages": [int...], "assembly_status": "complete|uncertain", "validation_status": "passed|failed", "reasons": [str...]}`
  - id = exam-file position k (= result.json question id); printed = refined q["id"] / segmented q["n"] (as `_printed` formats restarts: "s2.1").
  - source_pages = sorted({page} | continued_pages) for refined; [] for text path.
  - assembly_status = uncertain iff why has cut_unresolved, orphan_on_page *, merge_suspect or unreadable; else complete.
  - validation_status = failed iff why non-empty (exactly the questions that carry the `[Incomplete:` marker); reasons = why.
- Sidecar file wrapper: `{"schema": "assembly/1", "exam": "<basename of exam-out>", "questions": [rows]}`.
### 60.2 Writer (owner: cli.py ingest, after :520-522)
- When `--exam-out` is written and the source is not an exam-format Markdown: write `<exam-out>.assembly.json`. No new flag.
### 60.3 ingest-inspect table (owner: inspect.report, inspect.py:87-140)
- New `## Assembly` section before the disclaimer: `| id | printed | pages | assembly | validation | reasons |` from `api.assembly(doc, {"use_refined": "refined" in doc})`; omitted when doc has no questions and no refined. Read-only.
### 60.4 Plan input copy (owner: planrun.PlanWriter.start :96, import_dir :277-280)
- If `<exam>.assembly.json` is a plain file next to the exam: copy to `input/assembly.json`. Absent: no change. Report reading it = out of scope.
### 60.5 refine.md rule (owner: prompts/dev/ingest/refine.md, new rule 12)
- "12. Never transcribe running headers, footers or page numbers (school or exam name, exam code, \"Page 2/4\")." (~20 tokens per refine call).
### 60.6 system.md decline line (owner: prompts/dev/system.md:7-8 and prompts/dev/lang/vi/system.md:7-8)
- New bullet after the ambiguity rule: "- A question that is incomplete (cut text, missing option, figure or passage) or merged with another: `answer_status` `unanswerable`, `answer: null`, `issues` starting `missing_text:`." Same meaning in vi.
- Cost: ~30 tokens (en) / ~50 (vi) per solve call, system prompt is sent once per call.
- Release: dev only in TASK-048. A release `v1.3.0` + engine.json `prompt_release` bump changes every default solve and the golden outputs -> separate user decision (Q1).

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| Sidecar write fails (OSError) | ingest exits 2 like exam-out errors | `ERROR: ingest: ...` |
| Old doc / refined.json without page | source_pages [] | table shows `-` |
| Renderer and sidecar drift | impossible by `_selected` reuse; test 3 bites | test fail |
| Solver ignores the new line | gate still declines marked ones | as today |

## Unit tests (tests first, mock only, tier 0; 2-page fixtures F2/F3 from gold_pdf split layout + a hand-built refined doc)
1. assembly on 2-page refined doc: question cut p1 + continued p2 -> source_pages [1,2], complete, passed.
2. cut without continuation -> uncertain, failed, reasons ["cut_unresolved"]; orphan -> uncertain.
3. For every row: validation_status failed <=> `[Incomplete:` marker in that question block of to_exam_text (same doc).
4. Golden: to_exam_text bytes for every examples/ source and existing fixtures unchanged before/after the `_selected` refactor.
5. cli ingest --exam-out writes `<exam-out>.assembly.json` (schema assembly/1, ids 1..N); Markdown exam source -> no sidecar.
6. ingest-inspect report contains `## Assembly` row per question; doc without questions -> no section.
7. PlanWriter.start / import_dir copy the sidecar to input/assembly.json when present, not when absent.
8. Prompt files: dev system.md (en, vi) contain `missing_text:`; refine.md has rule 12; test_prompt_channels / test_prompt_variants / test_ingest_refine prompt_sha256 tests pass; release v1.0.0 files untouched (verify_release empty).
9. Solve tests unchanged: full suite `python3 -I -m unittest discover -s tests/unit` OK with no expectation edits outside new tests.

## Verification
| Item | command -> expected | tier |
|---|---|---|
| 60.1-60.6 | `python3 -I -m unittest discover -s tests/unit` -> OK | 0 |
| 60.2/60.3 | ingest on a 2-page fixture PDF with `--refined` mock file, then ingest-inspect -> sidecar rows and table match | 0 |
| AC3 | `git diff --stat` of examples/ goldens empty; result.schema.json unchanged | 0 |
No paid run.

## Decisions
- Sidecar + inspect (A) - fields in result.json (closed schema, version bump) rejected - inspect-only rejected (no machine link).
- `_selected` extraction - recomputing in assembly rejected (drift).
- Text-path pages []: line->page map in pdf.py rejected for now (G1, bigger change).
- Prompt: one bullet - guide's 8-line block rejected (~120 tokens).

## Gaps
- G1 text path has no per-question page; sidecar shows []. Follow-up if wanted: pdf records line->page, segment keeps `pages`.
- G2 coder: confirm the `--refined` JSON is a full doc that passes validate_document (ingest-inspect on it); else inspect gains `--refined FILE` like ingest.
- G3 a solver `unanswerable` with `missing_text:` issue: check engine reason/metrics.py:144 `declined_missing_text` counts it; if not, leave (no engine change in scope) and note.
- Q1 (user): release v1.3.0 + default bump now, or dev only? Recommend dev only (golden stability; bump in a later prompt-release task).

## Defects
- I1 (info, config/engine.json:1): default `prompt_release` is v1.0.0 while v1.1.0 and v1.2.0 exist; prompt changes since v1.0.0 do not reach default solves. Confirm intended.
- I2 (low, api.py:147-150): `Source pages` only for guide questions; plain refined questions get none in exam text (sidecar covers it; no exam text change to keep goldens).

## Out of scope
Report rendering of the sidecar; line->page map for the text path; prompt release bump; engine decline logic changes.
Nova

## Decisions (coordinator)
- Q1 accepted: the prompt lines (refine.md rule, system.md decline wording) go to the dev channel only; the frozen release stays v1.0.0 until the user promotes a release. Editing refine.md voids cached refine pages (cache key has the prompt hash): state it in the report.
- Text-path questions get `source_pages: []` (G1, no page data exists); documented, not guessed.
