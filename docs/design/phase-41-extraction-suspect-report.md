# Phase 41: extraction-suspect report and referenced-part check (TASK-041; REQ-0044)
# Draft: Phase 41 - extraction-suspect-report (TASK-041, REQ-0044)
Target doc: docs/design/phase-41-extraction-suspect-report.md (main writes). Tier 0, $0.

## Goal
- `ingest-inspect` on a refined doc lists, per section, the questions whose extracted text looks incomplete, with reasons; a solver decline on such a question says `missing_text` in `status_reason`.
- Known when: refined3.json run flags printed 23 (new check) + 10, 66 (existing signals); new check flags <= 2 clean questions.

## Constraints
- needs_review semantics/value untouched (refine.py:262 unchanged); refined docs not rewritten; no re-refine needed.
- No change to solver prompts, exam text, result/ingest schemas (AC4). `status_reason` is a free string (schemas/result.schema.json:249).
- Inspect without `doc["refined"]` → byte-identical report (existing tests guard).
- No real question text in tests/design (copyright).

## Design
### 41.1 Pure check (owner: new src/exam_engine/core/refcheck.py; core = pure, no model, no key, importable by ingest and engine)
- `referenced_parts(text, shared_figure=False) -> list[str]`: missing refs, e.g. `["paragraph (5)", "figure/table"]`; empty = clean. Input = question block WITHOUT options (same as parser.py:72 `text`).
- `missing_by_question(texts) -> list[list[str]]`: per text; `shared_figure` = another text with the same first non-empty line (= the shared passage copied by api._share_context) has a figure/table. Needed: printed 97-99 share one chart whose `[Figure/table:]` line is on 97 only.
- Paragraph refs (case-insensitive, `re` Unicode `\b`):
  - VI `\bđoạn(?:\s+(?:văn|thơ|trích))?\s*\((\d{1,2})\)` (parenthesized) and `...\s+(\d{1,2})\b` (bare).
  - EN `\bparagraph\s*\(?(\d{1,2})\)?`.
- Paragraph markers: `(?m)^[\s"“”'‘’*_\-\[]*\((\d{1,2})\)\s` (line-start `(N)`, optional opening quote: DGNL uses `“(1)`).
- Flag `paragraph (N)` when: markers non-empty and N not in markers; OR markers empty and the ref is parenthesized (VI `đoạn (N)` implies a numbered passage).
- NOT flagged (deliberate): bare `đoạn 3` / `paragraph 2` with no markers (DGNL English uses unnumbered passages: ~14 refs, all clean); bare `(5)` anywhere (formulas, lists: counted only as a marker, which can only remove flags); refs inside options; second numbers of a list (`đoạn (2), (3)` checks only 2).
- Figure/table refs (deictic only): VI `\b(hình|bảng|biểu đồ|đồ thị|sơ đồ)(\s+vẽ)?\s+(bên|dưới|trên|sau|\d+)\b`, `bảng số liệu`; EN `\b(figure|table|chart|graph|diagram)\s+(above|below|\d+)\b`, `\b(following|above|below)\s+(figure|table|chart|graph|diagram)\b`.
- Figure satisfied by: a line starting `[Figure/table:` (api.py:147), a Markdown table row `^\s*\|.*\|`, or `shared_figure`. Number not matched (`Figure 1` vs description): any figure satisfies.
- NOT flagged: bare `hình` (hình chữ nhật/chóp/vuông = shapes), `đồ thị (C)` (function graph), bare `bảng`/`biểu đồ`, `table` without `\b` (suitable).
### 41.2 Refined question blocks (owner: ingest/api.py, refactor only)
- Extract from `_from_refined` (api.py:121-128 merge + :135 share) `refined_questions(doc) -> list[q]` and from :144-147 `question_lines(q) -> list[str]` (context, "", text, "", figure lines). `_from_refined` calls both; its output byte-identical (existing api tests + diff of e3 regeneration in 41.5).
### 41.3 Suspect list + report (owner: ingest/inspect.py)
- `extraction_suspects(doc) -> [{"id", "part", "page", "reasons": [str]}]`, only questions with >= 1 reason; `[]` when no `refined`.
- Reasons (codes first, detail after a space): `referenced_part_missing paragraph (5)` / `referenced_part_missing figure/table` (41.1 on `question_lines`); from existing fields: `low_similarity 0.475` (similarity < refine.MIN_SIMILARITY), `joined_page 15`, else `needs_review` (gap/unreadable: cause not stored). needs_review = OR over raw entries of the same id (a page-split question keeps any flag).
- `report(doc)`: header line `- extraction suspects: K of M refined questions` and section `## Extraction suspects` with `### <part or "no part">` groups, rows `- printed N (p7): reason; reason`, sorted by printed number. Both only when `doc["refined"]` exists.
- No doc warning added (rejected: changes saved docs, needs re-refine/schema check). `suspicious()` unchanged.
### 41.4 Decline reason (owner: engine.py build_result :58-75)
- Before building rows: `miss = refcheck.missing_by_question([q["text"] + "\n" + exam["passage"] ...])` in exam order. If `r["reason"] == "solver_declined"` and `miss` non-empty → `r["reason"] = "solver_declined: missing_text (" + ", ".join(miss) + ")"`.
- Here because decide_rec is re-run in verifier.py:210, scorer.py:124, engine.py:128; build_result is after all of them and after every prompt → no prompt/solve change. retry_ids (:52) unaffected (status unchanged).
- Status reason only; no new finding (qa_findings shape untouched). Other UNCERTAIN reasons not rewritten (AC3 names declines).

## Failure modes
| Failure | Response | Operator sees |
|---|---|---|
| refs regex misses a variant (e.g. `khổ thơ 2`, `[1]` markers) | not flagged | needs_review/other reasons only |
| question number at line start `(3) ...` counted as marker | fewer flags | possible miss |
| no `refined` in doc | no section | report as today |
| refined malformed (no context key) | `.get` defaults | no crash |

## Unit tests (tier 0, synthetic placeholder text only, write first)
- tests/unit/test_refcheck.py: VI `đoạn (5)` with markers (1)-(4) → `["paragraph (5)"]`; same with (1)-(5) → `[]`; marker after `“` counts; markers {1,2,4} + ref 3 → flagged; EN `paragraph 2` no markers → `[]`; VI `đoạn (2)` no markers → flagged; bare `(5)` in a formula → `[]`; `hình chữ nhật`, `hình chóp`, `đồ thị (C)` → `[]`; `Sơ đồ dưới đây` no figure → `["figure/table"]`, with `[Figure/table: x]` → `[]`, with `| a | b |` → `[]`; `the table below` → flagged, `suitable` → `[]`; `missing_by_question`: 3 texts same first line, figure on first only → all `[]`.
- test_ingest_inspect.py: doc with refined (one clean, one paragraph-missing, one similarity 0.4, one joined_page) → suspects ids/reasons exact; report has the section and count; doc without refined → report equals current output (snapshot of existing fixture).
- api tests: `_from_refined` output unchanged on an existing fixture after 41.2 refactor (existing tests must pass untouched).
- test_exam_run.py: mock solver declines a question whose text names `đoạn (5)` with (1)-(4) → status_reason starts `solver_declined: missing_text`; declined clean question → exactly `solver_declined` (existing :192 and test_exam_checks.py:153 untouched); answered flagged question → reason unchanged.
- Full suite: `python3 -I -m unittest discover -s tests/unit`.

## Verification (main runs; tier 0)
| Item | Command → expected |
|---|---|
| 41.1/41.3 AC1-AC2 | script `work/TASK-041/flagged.py` (untracked, prints numbers + codes only): load refined3.json, `inspect.extraction_suspects(doc)` → refcheck-flagged = {23, 66}; all suspects = {6, 10, 23, 66, 67, 89, 102}; clean questions flagged by the new check = 0 (target <= 2). Save via save-evidence.sh. |
| 41.2 | regenerate e3-*.md from refined3.json with the same --pages/--meta → `cmp` identical to current files |
| 41.3 | `python3 -I exam.py ingest-inspect work/dgnl-real/refined3.json --out /tmp/x.md` → `## Extraction suspects` with 7 rows, 23 reason `referenced_part_missing paragraph (5)` |
| 41.4 | unit test above (no paid run) |
- Prediction basis: grep of e3-*.md with the 41.1 patterns: paragraph refs only in Vietnamese 21-28 (23 is the only N outside its markers) and English (no markers); deictic figure refs only in Math 65 (has figure) and 66 (none). Main must confirm by script.

## Decisions
- New check in core/refcheck.py, not inspect.py: engine (pipeline) must use it; core holds pure helpers (decision.py) - inside inspect.py would make engine import ingest.
- Suspects computed at inspect time (read-only) - rejected: `suspect_reasons` stored by refine (needs re-refine, schema), doc warning code (same).
- Decline suffix in build_result - rejected: decision.decide (no question text), solver.solve_round (overwritten by later decide_rec).
- Sections = refined `part`; DGNL refined3 has `part: null` for all 120 → one group "no part" (AC3 per-section holds only nominally). Option for main/user: group by page ranges given on the CLI (`--sections 1-30,31-60,...`) = new input, not proposed.

## Risks
- Language variants (`khổ`, `câu thơ`, `Paragraph B`, `[2]` markers) missed: FN only.
- Shared-group key = first line: two unrelated questions with the same first line would share a figure (FN only).
- MIN_SIMILARITY default used; a refine run with `--min-similarity` other than 0.6 shows different `low_similarity` rows than its needs_review (shown as `needs_review` fallback - no wrong claim).
- 10 has no referenced-part signal of its own (lost stem); relies on needs_review.

## Out of scope
- Fixing the cut text (refine continuation): REQ-0043. Sharing figures to grouped questions in exam text (would change solving, AC4). Cache: no cached prompt/query body changes.

## Defects
- D1 (low, ingest/refine.py:262): needs_review cause (unreadable vs numbering gap) not stored, so inspect can only say `needs_review`; not fixed here (needs_review semantics frozen).
- D2 (low, ingest/api.py:109 `_share_context`): shares context but not `figures`; grouped questions 98-99 see the chart text only on 97. Recorded, not changed (AC4).
- D3 (info, refined3.json): `part` null for all questions → per-section grouping degenerates (see Decisions).

## Coordinator note
Decision accepted: no `--sections` input; per-section report collapses to one group when `part` is null. Coordination with REQ-0043/TASK-040 (multi-page assembly, user RAW-00144): refcheck is the shared completeness check; TASK-040 reuses `core/refcheck.py` instead of writing its own.
