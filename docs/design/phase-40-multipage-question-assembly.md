# Phase 40: multi-page question assembly (TASK-040; REQ-0043)
# Draft: Phase 40 - question assembled over any pages (TASK-040, REQ-0043 AC1-AC6, RAW-00144/00145)
Suggested path: docs/design/phase-40-multipage-question-assembly.md
## Goal
- A question (stem, passage, figure/table, options) cut over 1..N pages/images/tiles is assembled whole before solving; an unassemblable one is declined deterministically with `missing_text`, never guessed.
- Seen when: re-extract of PDF p.4-7,14-15 gives printed 10, 23, 66, 21-25 complete vs work/TASK-039 indep reads; counts per section unchanged.
## Constraints
- Old refined.json (work/dgnl-real/refined3.json) loads unchanged: every new field optional, default = today's behaviour.
- Refine prompt is read from prompts/dev/ingest/refine.md only (refine.py:23); no release copy exists, none to update.
- No new model calls; stdlib only; no key in prompts.
## Current model (facts)
- One vision call per page (refine.py:227-263). `carry` = passage forward to the next page's first numbered question (:236-241).
- Backward only for options: entry `id:""` joins the last option-less question (:242-248); same id on two pages joined in api.py:123-126.
- Missing: stem/figure/passage paragraphs at the top of page N+1 (dropped or misfiled), chains over 3+ pages, owner check (any earlier option-less question, not page N-1's last).
- DOCX: one logical page in file order (docx.py:1); page/section breaks = newline (:53), tables inline (:184), inline images as blocks (:150); text boxes SKIPPED (:43-47, doc-level `unsupported_content` only). segment.py:27-31 appends every unnumbered line to the open question = backward continuation is native.
- Images: one file = one page n=1 (image.py:198); refine renders PDF only (cli.py:338-340).
## Options
| Opt | Mechanism | Cost/exam (22 p) | Risk |
|---|---|---|---|
| A (chosen) | reply gains top-level `continues` {text, options, figures, passage} = content above the first printed number; bridge attaches it to the open question of page N-1 (or pending carry); chains | 0 extra calls, ~22 x $0.04 = ~$0.9 (as today), +~3% prompt tokens | model files top content in wrong field -> guarded by owner rule + completeness check |
| B | send page N-1's last question as text context; model returns it completed | same calls, +10-20% tokens | model rewrites/duplicates earlier text, changes clean output, 3-page chains need recursion, owner implicit |
| C | 2nd call with 2 images only for pages a cut detector flags | +~$0.08 per cut page | detector misses (needs_review missed 23, 24-25: phase-39 report :26), 2-image call path new, N-page chains need N images |
- A: why better: the model only transcribes what it sees on one page (same trust model), the join is deterministic, chain-safe by induction, testable at tier 0 with mock replies. C's detector is reused as the completeness check (40.4) without a second call; C stays a later fallback if 40.4 flags remain after re-extract.
## Design
### 40.1 Refine reply + prompt (owner: prompts/dev/ingest/refine.md, refine.validate_refined :142)
- Reply: `"continues": {"text":"","options":{},"figures":[],"passage":false}` (optional; absent = empty); per question `"cut": true|false` (optional, default false).
- Prompt rules (replace 8, extend 9): (a) everything printed above the first question number that continues the previous page (rest of a sentence, its figure/table, its options, more passage paragraphs) goes in `continues`, never in `questions`, never with a number; `passage:true` when it is passage text; (b) a page with no question number at all puts everything in `continues` (or `carry` if it is a new passage for later questions); (c) `cut:true` when a question visibly runs past the page bottom; (d) a figure/table printed before the first number belongs to `continues` only if it continues the previous question, a shared figure for the following questions goes into the first question that uses it; (e) a line cut at the top/bottom edge: transcribe the readable part, `unreadable:true`.
- validate: `continues` must be an object of the same shapes as a question (strings/options dict/figures list/bool); `cut` bool. Legacy `id:""` entries still valid and mapped to `continues.options` (old mocks keep passing).
### 40.2 Bridge (owner: refine.refine loop :226-263, new helper `_attach(state, n, cont)`)
- State across pages: `open` = (page, index in qs) of the last question emitted by the last processed page; `carry` (exists).
- Owner rule (wrong-owner guard): attach only when the previous processed page == n-1; else `orphan`.
- Order per page: 1) cont with `passage` and a pending carry -> append to carry; 2) else cont -> `open` question: text appended (or `context` when `passage` and the owner has context), options set only if owner has none (else orphan), figures appended; owner gets `continued_pages += [n]`, `needs_review` unchanged unless orphaned; 3) carry -> first numbered question (as today); 4) if the page has no numbered question, `open` stays the same question, its page pointer moves to n (chain over N pages); pending carry stays pending.
- Duplicate guard: drop a continuation prefix equal to the owner's folded suffix (>= 20 chars, tile overlap); a continuation already contained in the owner -> skipped.
- Number guard: cont text starting with a question number (segment._Q) -> orphan, never merged.
- Orphans -> `refined["orphans"]` [{page, kind}] + warning `orphan_continuation` naming page n-1 to add to `--pages`; the CLI line (cli.py:423) prints the count.
### 40.3 Shared assembly for image sequences (owner: adapters/image.py, cli._refine_source :325)
- `image.ingest_sequence(paths) -> doc`: each file = page k (1..k in the given order), blocks via existing `ingest`; source format `image_seq` with per-page name+sha256. Tiles of one tall image = a sequence (same rule, overlap handled by 40.2 duplicate guard).
- `render(path, n)` for image_seq = bytes of file n, shrunk by `imgmod._shrink` (:91). `ingest-refine FILE [FILE...]`; refine loop unchanged (same 40.2 bridge).
### 40.4 Completeness check (owner: core/refcheck.py from TASK-041; new `incomplete_reasons(q, shared_figure=False) -> list[str]`)
- Reasons: `options_incomplete` (1-3 of A-D); `cut_unresolved` (cut true and no continuation attached); `referenced_part_missing ...` = TASK-041 `referenced_parts()` (call it, never re-implement; if TASK-041 is not merged, 40.4 lands after it: dependency, not a copy); `orphan_on_page N` for the open question of an orphaned next page.
- Computed at render time (api.py `_from_refined`/`refined_questions` of TASK-041 41.2) from stored fields, so old refined.json get the check without re-extract; stored copy `incomplete` written by refine for inspection only.
- Same function on segmented questions of DOCX/PDF text (`_from_questions` api.py:165) for options/referenced parts (no `cut` there).
### 40.5 Incomplete -> deterministic decline (owner: api.py render + engine.py solve loop)
- Exam text: one line `[Incomplete: missing_text <reasons>]` after the question text (FORMAT.md gets one line documenting it).
- engine: ids whose question holds the marker are not sent to the solver; rec status `UNCERTAIN`, reason `solver_declined: missing_text (<reasons>)` (same string as TASK-041 41.4, so one grep finds both).
### 40.6 DOCX (owner: adapters/docx.py `_text` :38)
- Same rule, different mechanism: no vision bridge; file order + segment already assembles across page/section breaks, tables and inline images.
- Change: text-box text read inline at its anchor (own line), not skipped; warning becomes info `text_box_inlined`. Floating content that still is not read -> the question it references is caught by 40.4 and declined.
### 40.7 Skill `exam-extraction` (owner: main writes .claude/skills/exam-extraction/SKILL.md; outline <= 40 lines)
- A question is one unit over any number of pages, images, tiles or DOCX breaks; never solve a fragment.
- Per source: PDF/images = per-page vision + `carry` forward + `continues` backward, owner = last question of page N-1 only; DOCX = file order, text boxes inline.
- Always select the page before a continuation (`--pages` N-1..N); orphan warning = re-run with N-1.
- Never repeat or renumber; never move content to a later question to fill it.
- After assembly run the completeness check; incomplete -> `missing_text`, never guess.
- Figures: describe kind under `figures`; a reference to a figure needs one present.
- Check: printed counts per section unchanged; compare with an independent read before claiming fixed.
- Prompt rules (40.1) and code (40.2-40.6) must match this list; a change to one updates all.
## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| continuation for wrong owner (page N-1 not refined) | orphan, not merged | warning orphan_continuation page N, add N-1 |
| model puts top content in `questions` without id | legacy path -> continues.options/text | as today; 40.4 flags leftovers |
| duplicated text (tile overlap, model repeats) | prefix trimmed / skipped | nothing; test 8 |
| figure with no owner | orphan; referencing question incomplete | warning + `missing_text` decline |
| owner already has A-D, continuation has options | orphan, needs_review | warning |
| 40.4 false positive (math stem) | decline instead of answer | `missing_text` reason; only structural signals used, no punctuation heuristic |
## Unit tests (tier 0, write first; mock replies via iter + namedtuple C as test_ingest_refine.py:477-483)
1. stem split: p1 q6 cut, p2 continues.text + options -> one q6, text joined in order, options A-D, continued_pages [2].
2. figure at top of next page: continues.figures -> owner figures, rendered `[Figure/table:` line.
3. passage over 3 pages: p1 carry, p2 continues passage only (no numbers), p3 continues passage + q1 -> q1 context = 3 parts in order.
4. options on a third page: p1 stem cut, p2 continues figure only, p3 continues.options -> one question, A-D.
5. no continuation: replies without new fields -> refined questions byte-equal to today (golden from current code).
6. wrong owner: pages 1,3 refined, p3 continues -> orphan, nothing merged, warning names page 2.
7. old refined.json: refined3-shaped dict without new fields -> `_from_refined` output equal except marker lines from 40.4 only where reasons exist.
8. duplicate guard: continuation repeating owner suffix -> once.
9. number guard: continuation starting with a number -> orphan.
10. image sequence: 3 PNG fixtures (tests/fixtures tiny PNGs) -> pages 1-3, render returns file n; scenario 1 over images passes.
11. completeness: options_incomplete, cut_unresolved, referenced part via refcheck; complete question -> [].
12. decline: marked id never in solver prompt (mock solver asserts), reason `solver_declined: missing_text (...)`; unmarked ids unchanged.
13. DOCX: question with stem, page break, table, text box, then options -> one question with the text-box line; passage over 2 page breaks shared.
14. legacy `id:""` reply still joins (existing test :453 kept).
## Verification
| Item | command -> expected | tier |
|---|---|---|
| 40.1-40.6 | `python3 -I -m unittest discover -s tests/unit` -> OK | 0 |
| 40.2 real | `python3 -I exam.py ingest-refine examples/dgnl/De-thi-minh-hoa-2026-Final.pdf --pages 4-7,14-15 --all-pages --real --max-cost-usd 0.5 --out work/TASK-040/refined.json` -> 6 pages, ~$0.25 (add the page of 21-25 if outside 4-7, see work/TASK-039 evidence) | paid, user go RAW-00144 |
| AC4 | main/verifier compares printed 10, 23, 66, 21-25 in the new exam text with work/TASK-039/handoff/indep-*.md and work/dgnl-real: stem sentence, graph described, paragraphs incl. 5 + attribution present; 0 orphans | read |
| AC3 | merge new pages into refined3 (other pages untouched): per-section counts equal; clean questions' text byte-equal (diff) | 0 |
| 40.5 | inspect output: remaining incomplete ids listed with reasons, none of 10/23/66 | 0 |
## Decisions
- A over B/C (above). Completeness computed at render, not stored-only (old files covered). Decline in engine, not prompt (deterministic).
## Risks
- Solve cache: confirm the cache key includes the rendered question text (marker line changes it); else stale answers for 10/23/66 reused.
- 40.3 is the largest piece (new CLI arity); if main wants smaller, ship 40.1-40.5 and 40.3 as follow-up task (ask user).
- 40.6 text boxes used as decoration add stray lines -> covered by segment (non-numbered lines stay in the open question).
## Out of scope
- Two-image "read adjacent pages together" call (option C); tiling a tall image ourselves; headers/footers/footnotes of DOCX; solver prompt changes.
## Defects
- D1 (high, refine.py:244): legacy option join picks the last option-less question anywhere in `qs`, not page N-1's last question -> options can attach to a wrong earlier question; fixed by 40.2 owner rule.
- D2 (high, refine.py:242-248): top-of-page stem/figure/passage text with `id:""` but no options is dropped silently (only options carried) -> printed 66 loss pattern.
- D3 (medium, docx.py:43-47): text-box content skipped with only a doc-level warning; the owning question is not marked -> solved from a fragment.
- D4 (low, cli.py:338): refine refuses image sources, so image exams cannot be re-extracted at all (40.3).

## Coordinator decisions
1. Split by risk (quality first): TASK-040 = 40.1, 40.2, 40.4, 40.5, 40.6, 40.7 (PDF continuation, completeness check, DOCX text boxes, skill); TASK-042 = 40.3 image-sequence refine (`ingest-refine FILE [FILE...]`, D4), same bridge, queued right after. REQ-0043 closes only when both are DONE (user RAW-00144/00145: pictures and docx are in scope, never left as a defect).
2. Depends on TASK-041 (`core/refcheck.py`): TASK-040 is picked after TASK-041 is DONE.
3. Solve cache: the rendered question text MUST be part of the cache key (design risk); the tester checks it with a case where a question text changes but id and subject do not.
4. Paid real run (about 8 pages, about $0.3, user go RAW-00144) only after the tier-0 tests pass: pages around printed 10, 23, 66, 21-25 (PDF pages 5-7, 14-15 and the pages of 21-25); compare with work/TASK-039 independent reads; section counts unchanged.
