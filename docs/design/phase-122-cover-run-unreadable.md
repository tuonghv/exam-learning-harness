# Phase 122 – DGNL26 text path: cover run and image-only question (TASK-122, REQ-0129)

Draft: work/TASK-122/handoff/design.md.

## Goal
DGNL26 text path: 120 questions (cover headings `1`,`2` become intro), q4 (`Câu 4:` + picture) kept and
declined as missing_text, doc no longer `segmentation_skipped`. Other PDFs and examples/ byte-identical.

## Constraints / Generality
- Rules use only numbering + option presence; no exam, subject or language literal. Covers every adapter
  that calls `segment.segment` (pdf.py:693, docx.py:213, parts.py:104 via boundary.py:426/430).
- Source text never edited; `ok` keeps its meaning (consecutive 1..k AND all text) -> callers unchanged.
- No cache key touched (segment is pure; boundary hint cache keys on lines, unchanged).

## Plan modes
- text path (pdf/docx/parts): affected, both rules, via `segment` + `numbering`.
- refined path (`use_refined`, refine.py): not affected (own `unreadable` field already validated refine.py:237-243).
- markdown examples/: not affected (no `segment` call); oracles confirm.
- solve/engine: no change; declines through the existing marker (see 122.2).

## Design
### 122.1 Cover run -> intro (owner: segment.py `segment`, end, before `ok` at :337)
- Track start indices always: `st = starts if starts is not None else []` (replace the two `if starts is not None` appends, :271/:294).
- After the trailing-pending block (:332-336): `rs = runs(qs)`; k = len(rs[0]). Fire when
  len(rs) >= 2 and no question of rs[0] has options and some question of rs[1] has options
  and len(rs[0]) < len(rs[1]) (guard, see Open question).
- Effect: `intro = lines[:cut]`, `qs = qs[k:]`, `st[:] = st[k:]` (caller's list trimmed in place).
  `cut` = st[k] when qs[k] has no context, else the line where qs[k]'s context starts:
  walk back from st[k]-1 counting non-blank lines until len(context.split("\n")) are seen
  (pending holds exactly the non-blank lines before the start, :255/:313/:317/:325/:327).
  New private helper `_ctx_start(lines, end, n)`.
- So: cover text + its context ('Phần 1. ... (60 câu)') land in intro verbatim (source lines);
  the real q1 keeps its own context 'PHẦN 1: ...\n1.1. TIẾNG VIỆT' (no duplication).
- `ok` then computed on the trimmed qs (DGNL: 1..120 -> still False only because of q4, see 122.2).
- Minimal: one block at the end, reuses `runs`; no change to the line loop or hints logic.
- Risk: an exam whose first numbered section is option-less (essay part 1..k, then MCQ restarting at 1)
  loses part 1 to intro. Guard len(rs[0]) < len(rs[1]) limits it; oracle over 4 PDFs + examples shows impact.

### 122.2 Empty-text question kept as unreadable (owner: segment.py `segment` end + `numbering` :388)
- Representation used downstream: `q["unreadable"] = True` (refcheck.py:126 -> reason `unreadable`;
  api.py:359 UNCERTAIN; marker `[Incomplete: missing_text unreadable]` via refcheck.marker, api.py:415;
  engine.incomplete_ids engine.py:110 -> `solver_declined: missing_text (unreadable)` engine.py:390).
- segment, after 122.1: for q in qs with empty text: `q["unreadable"] = True`. `ok` formula unchanged
  (still False) -> pdf.py:700 falls to `numbering(...)["usable"]`.
- numbering :388 `sane`: `all(q["text"] or q.get("unreadable") for q in qs) and any(q["text"] for q in qs)`
  (at least one real question). Run/number checks unchanged, so an empty question counts only when its
  number fits the run (consecutive / increasing as today).
- Downstream check: `_gate` (api.py:260) only filters on `verification`; the record passes, refcheck flags
  it, exam text gets the marker line, engine declines it (never sent to the solver: engine.without_questions).
  assembly row: uncertain/failed with reason `unreadable`. No solve change.
- Minimal: one flag set + one predicate; reuses the existing unreadable -> missing_text decline chain.
- Risk: a broken text layer with many empty questions becomes "usable" with many declines instead of
  segmentation_skipped. Detected by the per-question decline count (metrics declined_missing_text) and the
  page `missing_text` warning that such docs already carry.

## Unit tests (synthetic, tests/ for segment; no DGNL text)
- T1 cover: lines `1. Structure`, `2. Strategy prose`, `Part 1 (3 items)`, `PART 1`, `1. Q a`, `A. x`..`D. x`,
  `2. Q b` + A-D -> 2 questions n=[1,2]; intro has `1. Structure`..`Part 1 (3 items)`; q1 context == `PART 1`;
  `starts` length 2 and points at the real starts.
- T2 no fire: leading run with options (math style 1-2 MCQ, then 1-2 short answer) -> unchanged runs [[1,2],[1,2]].
- T3 no fire: both runs option-less (essay parts) -> unchanged.
- T4 guard: option-less leading run longer than the next -> unchanged.
- T5 empty: `1. a`+A-D, `2.` alone, `3. c`+A-D -> 3 questions, q2 text "" and unreadable True, ok False,
  numbering usable True, numbering_warnings [].
- T6 all empty: `1.` `2.` -> usable False (any-text guard).
- T7 decline chain: api exam text of a doc with an unreadable q carries `[Incomplete: missing_text unreadable]`
  under that question; engine.incomplete_ids returns it.
- Existing numbering / segment tests stay green (AC3).

## Verification ($0)
| Item | Command -> expected |
|---|---|
| 122.1+122.2 DGNL26 | main re-ingests input/dgnl/De-thi-minh-hoa-2026-Final.pdf -> 120 questions, intro starts 'Cấu trúc đề thi', no `segmentation_skipped`/`numbering_restarted`; q4 unreadable, exam text has the marker under Question 4 |
| AC3 PDFs | same ingest of DGNL25, DHQG24, math PDF old (HEAD worktree) vs new -> questions/intro/warnings identical |
| AC3 examples | `python3 -I work/TASK-114/evidence/oracle.py <old-src> .` vs `<new-src>`, and `work/TASK-116/evidence/share_oracle.py` same -> diff empty |
| AC4 | `python3 -I tools/run_tests.py --fast` -> NEW 0 |

## Decisions
- Rule in `segment` (not pdf.py): one place for pdf, docx, parts; `starts` stays parallel.
- `unreadable` (existing field) over a new `missing_text` key: the decline chain already handles it.
- No new doc warning: decline is visible in assembly rows and the exam marker.

## Out of scope
OCR of the q4 picture; refined path; any DGNL-specific heading text.

## Open question
- Q1: cover guard `len(rs[0]) < len(rs[1])` (recommended) vs the brief's rule without a size guard.

## Defects
none

## Coordinator decisions
- 122.1 guard (both required): the designer's `len(rs[0]) < len(rs[1])` AND a heading test: the first question of rs[0]
  has no part/section heading in its context (`segment.split_heading(ctx)[0] == []`) while the first question of rs[1]
  has one. DGNL26: cover q1 ctx '' vs real q1 'PHẦN 1: SỬ DỤNG NGÔN NGỮ'. An exam opening with an essay part under its
  own `PHẦN I` / `PART I` heading keeps its questions. Add a test for that shape (essay part with heading stays).

