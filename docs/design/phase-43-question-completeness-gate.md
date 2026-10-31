# Phase 43: question completeness gate, gap analysis and design (TASK-043; REQ-0045)
# Draft: Phase 43 - question completeness gate, gaps + design (TASK-043, REQ-0045 AC1-AC4)
Suggested path: docs/design/phase-43-question-completeness-gate.md
## Premise (facts at HEAD 05c18ec)
- PDF: native text per page, OCR only on flagged pages (pdf.py:1,240-262); all page lines joined, then `segment` once (pdf.py:316,324). Vision refine = 1 call/page (refine.py:307-311), only flagged pages unless `--all-pages` (refine.py:52-57).
- Assembly already state-based in effect: `st` open/page (refine.py:306,339-344) + `carry` (:316-338) + `_attach` owner rule (:264-288) = COLLECTING; `incomplete_reasons` (refcheck.py:71-85) = VALIDATING; marker (api.py:159-163,194-198) -> engine skip (engine.py:140-145, parser.py:176) = COMPLETE/UNCERTAIN.
- No cache of any kind in src/ (grep `cache` = 0). Refine trace = raw replies only, no page/hash (cli.py:418-420, refine.py:95).
- Solver rule already: ambiguous/unreadable/defective -> `unanswerable`, never guess (prompts/dev/system.md:7-8); phase-39 report :34: solver declined rather than guessed on extraction errors.
- Real evidence: needs_review caught 2/3 blocking (precision 2/6), missed 23, 24-25 (phase-39 report :26).
## 1. Gap table (have / partial / missing; cover: T40 bridge+completeness+DOCX boxes, T41 refcheck+suspects, T42 image seq)
| Guide area | Status | Evidence | Covered by |
|---|---|---|---|
| Pipeline parse->page extract->boundary->assembly->validate->solve | partial | pdf.py:324, refine.py:291, api.py:159, engine.py:140; no "extract next page" loop | T40 (all but recovery) |
| Boundary: numbering | have | segment.py:4,16-20; numbering gaps phase-38, refine `_gaps` refine.py:345 | phase-38 |
| Boundary: options A-D | have | segment.py:5,24-26; `options_incomplete` refcheck.py:77 | T40 |
| Boundary: section/subject headings | partial | parts.split_part refine.py:332; text path: heading after D glued into option D (segment.py:28-29) | - (D1) |
| Boundary: headers/footers/page numbers inside a question | missing | pdf.py:316 joins every line; refine.md has no rule (grep header/footer = 0); DOCX not read (docx.py:4) | - (D5) |
| Option D not an end signal | have (text) / partial | segment.py:28-29 continues D (right for wrapped options, wrong for passage intro/heading); vision `cut` refine.py:355 | T40 |
| Paragraph continuation across pages | have | text path native (segment.py:27-31); vision `continues` refine.py:236-288, chains :341-342 | T40 |
| Shared passages | partial | vision `carry` refine.py:316-338, group repeat api.py:101-112; text path passage intro lands in prev option D (D1); no `context` in segmented qs | T40 (vision) |
| Formulas/tables/diagrams kept | partial | math_possible keeps page image pdf.py:292; figure refs `referenced_parts` refcheck.py:32; no formula-truncation check | T41 |
| State-based assembly | have (implicit) | refine.py:306,339-344; states not named/recorded per question | T40 |
| Data: source_pages | partial | refined `page`+`continued_pages` refine.py:285,351; segmented qs: none per question (pdf.py:324 on joined lines) | T40 |
| Data: assembly/validation_status | missing (derived only) | reasons computed at render api.py:159, not exported; result.json qs closed schema (result.schema.json:123) | T41 suspects (inspect) |
| Validation: truncated formula (unbalanced ( [ { $, trailing operator) | missing | refcheck.py:71-85 has no such reason | - |
| Validation: tables/images referenced | have | refcheck.py:11-16,32 | T41 |
| Validation: merged/split questions | partial | split: same-id join api.py:119 + `_gaps`; merge: no check of a number inside a refined stem | phase-38/T40 |
| Validation: unreadable part | partial | `unreadable` -> needs_review only, not stored, not a reason (refine.py:353) | - (D2) |
| Recovery from next page(s) automatically | missing | orphan -> warning "add page N-1" only (refine.py:368-374); `cut_unresolved` -> decline | - |
| Cost: parse once | have | ingest once, refine reuses doc (refine.py:299,314) | - |
| Cost: cache page extraction | missing | no cache; each re-run pays every page | - |
| Cost: reprocess only uncertain pages | partial | `--pages` + flagged-only pick (refine.py:52-57); cut pages not flagged | - |
| Cost: Python first, AI for ambiguity | partial | OCR/flags Python; no Python cut detector, so `--all-pages` used on real exam | - |
| Solver QUESTION COMPLETENESS GATE | have (deterministic) / partial (prompt) | engine.py:140-145; system.md:7-8 lacks "incomplete/merged" | T40, T41 (reason) |
| Images assembled across files/tiles | missing (queued) | image.py one file = page 1; cli.py:338 refuses | T42 |
| Logging/traceability | partial | warnings + orphans refine.py:361-374, trace cli.py:418 (no page, no png hash: D6) | T40, T41 |
| Measurement of guide metrics | partial | extract_eval wilson/zero_error_n extract_eval.py:23-41,147; gold_pdf never splits a question (gold_pdf.py:79-84), no merge/decline metrics | phase-35/36 |
## 2. Design of remaining gaps (ordered by value/cost; all optional fields, old refined.json/doc.json load unchanged)
### 43.1 Text-path boundary fixes (owner: segment.segment, pdf._extract) - tier 0, $0
- Furniture filter in pdf.py before :324: drop from `all_lines` (blocks untouched) lines among the first/last 2 of a page whose digit-folded form repeats on >= max(3, half) pages, or that match a page-number pattern (`Trang/Page n[/m]`, `- n -`); info `page_furniture_removed` (count).
- segment.py:28: an unnumbered line after options that matches api.GROUP_RE (move to segment, api imports) or a part heading (parts.split_part) is NOT glued to D: it opens `pending_context`, attached as `context` of the next question; `_share_context` repeats it. Wrapped options keep today's join.
- Options: A furniture+GROUP only (chosen, deterministic, fixes D1/D5). B prompt the vision model for every page ($0.9/exam, text path stays wrong). C drop all repeated lines anywhere (deletes real repeated stems).
- Risk: a repeated real line at page top (e.g. instruction) -> only first/last 2 lines + >= 3 pages; test.
### 43.2 Completeness reasons (owner: refcheck.incomplete_reasons) - tier 0, $0
- `formula_unbalanced`: opens `([{` != closes `)]}` (counted together, so half-open intervals `[a;b)` stay balanced) or odd unescaped `$` in text+options; `trailing_operator`: text ends with `= + - × ÷ / ^ \` and no options. Only for questions with `cut`, `continued_pages` or last-on-page (refined `page` max), to keep false declines low.
- `merge_suspect`: a line inside the stem matches segment._Q with a number != own id, or two A-D option runs.
- `unreadable`: refine stores `unreadable: true` (refine.py:349-354, optional field) -> reason (fixes D2).
- Options: A reasons in refcheck (chosen: one function, render-time so old files get it, reuse T41 path). B a separate validator module (duplicate). C AI review of every question ($ per question, non-deterministic).
- Risk: math stems with unpaired bracket by design -> scoped to page-end questions; measured by 43.6 false-decline count.
### 43.3 Deterministic cut detector -> page selection (owner: pdf._extract warning + refine.FLAG_CODES :22) - tier 0
- Per page boundary n|n+1 (native text): S1 last question started on n has < 4 options and n+1 starts with a non-numbered, non-option line; S2 last content line of n ends without `. ? ! :` or with an operator; S3 n+1 starts unnumbered after furniture. S1 or (S2 and S3) -> warning `page_cut_suspect` on n and n+1; add to FLAG_CODES so `pick_pages` selects both.
- Options: A detector feeds selection (chosen: $0, Python first; refine of a 22-page exam drops from 22 to flagged+cut pages, ~8-12 x $0.04 = ~$0.3-0.5 instead of ~$0.9 when the user omits `--all-pages`). B vision on every page (today, ~$0.9, still no recovery). C detector replaces vision (text layer loses figures/math: rejected).
- `--all-pages` stays as is (user choice); detector never removes a page.
### 43.4 Bounded automatic recovery (owner: refine.refine, new `_recovery_pages(doc, pages, refined) -> list[int]`) - tier 0 code, paid pages
- After the loop: needed = {n-1 for orphan `no_owner`} | {page+1 for `cut` without `continued_pages`, page+1 in doc} minus pages done; at most K=2 extra pages per chain, 4 per run, inside `max_cost`; re-run the loop over sorted(pages | needed) with the per-run cache (43.5) so done pages cost $0. Never answer-key pages (check_key_pages). Warning `recovered_pages` lists them; `--no-recover` keeps today's behaviour.
- Options: A bounded re-run (chosen: reuses the loop and bridge unchanged, cost <= 4 x $0.04 = $0.16/exam). B decline-only (today; user must rerun by hand, 10/23/66 class stays declined). C 2-image adjacent-page call (new call path, phase-40 opt C, out).
- `owner_has_options` orphans: no recovery (needs human), stays decline.
### 43.5 Page-extraction cache (owner: refine._ask; cli `--cache DIR`) - tier 0
- Key = sha256(png bytes) + `prompt_sha256` + model (+ page n for mock b""); value = validated reply. Per-run memory cache always (needed by 43.4); disk only with `--cache DIR`; mock runs never read disk. Prompt change = new key (rule changes never reuse old answers).
- Trace rows gain `page`, `png_sha256`, `cached` (fixes D6).
- Options: A hash-keyed reply cache (chosen). B reuse refined.json pages by number (stale on prompt/model change). C none (each recovery/re-run pays again).
### 43.6 Provenance export (owner: api.py new `assembly(doc) -> [{id, printed, source_pages, assembly_status, validation_status, reasons}]`) - tier 0
- source_pages = [page]+continued_pages (refined) or pages of the lines (segmented: pdf records line->page map during :316, optional `pages` per question); assembly_status complete|uncertain (orphan/cut_unresolved); validation_status passed|failed (reasons).
- Used by `ingest-inspect` (table) and written as `<exam-out>.assembly.json` sidecar; result.json unchanged.
- Options: A sidecar + inspect (chosen: zero schema change). B fields in result.json (closed schema result.schema.json:123 -> schema_version bump, every consumer). C inspect-only (no machine-readable link from a result to pages).
### 43.7 Prompt lines (owner: prompts/dev/ingest/refine.md, prompts/dev/system.md) - tier 0
- refine.md: one rule "never transcribe running headers, footers, page numbers".
- system.md:7: add "incomplete (cut text, missing option/figure/passage) or merged with another question" to the decline rule; `issues` starts `missing_text:`. ~25 tokens per solve call; catches what the gate misses (23, 24-25 class). Rejected: the guide's full 8-line block (~120 tokens, "request extraction" impossible in a one-shot call). Release copy only via main's prompt release.
## 3. Measurement plan (owner: gold_pdf.render, extract_eval.evaluate) - tier 0 except V
- gold_pdf: `--layout split` lets a block cross the page at a line (today moves it whole, gold_pdf.py:79-84); gold records gain optional `pages: [p..]`. Fixture families (synthetic text only, never real exam text): F1 single page; F2 stem over 2 pages; F3 options on the next page; F4 passage over 3 pages + group of 3; F5 table/figure stand-in on next page; F6 4+ questions per page; F7 formula cut at the break; F8 header/footer/page number on every page.
- Scanned: render each page to PNG (fitz) -> image-only PDF -> ingest OCR (skipIf no tesseract); vision path: oracle mock replies generated from gold per page (tests bridge/recovery, not vision accuracy).
- extract_eval new rates (Wilson each): boundary = gold ids matched 1:1 with exact text start/end; cross_page = exact over gold with len(pages)>1; missing_detection = wrong extracted questions with reasons/total wrong; false_merge = extracted text holding another gold question's opening; incomplete_to_solver = wrong and unmarked (must be 0 on fixtures; any >0 = FAIL).
- Expected on fixtures (tier 0): F1-F8 x 25 questions = 200; boundary 200/200, cross_page = all split ones, false_merge 0, incomplete_to_solver 0.
- Honesty: 0 errors in n proves >= 99.9% at 95% only for n ~ 3000 (zero_error_n, extract_eval.py:34); report k/n with Wilson, never "99.9%". V (paid): vision on scanned gold, ~3000 q ~ 400 pages x $0.04 ~ $16, user go only.
## 4. Tasks (order)
| # | Where | Items | Tier | Acceptance |
|---|---|---|---|---|
| 1 | TASK-040 (now) | D2 store `unreadable`+reason; D3 same-id join keeps continued_pages/cut | 0 | unit: unreadable q marked; split same-id q not cut_unresolved |
| 2 | TASK-042 (queued) | image seq + 43.5 trace page/hash | 0 | phase-40 test 10 + trace rows have page |
| 3 | new TASK-044 | 43.1 furniture + group/heading after D | 0 | F8, F4 text path exact; old doc.json render unchanged |
| 4 | new TASK-045 | 43.2 reasons | 0 | F7 marked; complete fixtures 0 false declines |
| 5 | new TASK-046 | 43.6 gold split layout + eval metrics | 0 | F1-F8 rates as expected; incomplete_to_solver 0 |
| 6 | new TASK-047 | 43.3 detector + 43.4 recovery + 43.5 cache | 0 tests, paid ~$0.2 | mock: orphan/cut pages auto-added <= 4; re-run 0 calls cached; real DGNL subset 0 orphans |
| 7 | new TASK-048 | 43.6 sidecar + 43.7 prompts | 0 | sidecar per id; prompt sha changes, solve tests pass |
## Risks
- 43.1 changes text-path exam text for docs with furniture -> golden diff on examples/ before/after.
- 43.4 extra pages near answer key -> check_key_pages on recovered pages.
## Out of scope
- 2-image adjacent-page call; DOCX headers/footers; AI boundary review per question.
## Defects
- D1 (high, segment.py:28-29): unnumbered line after options always appended to last option: group-passage intro / part heading after D lands in option D; following questions lose the passage (PDF text, DOCX).
- D2 (medium, refine.py:349-354 + refcheck.py:71-85): reply `unreadable` only feeds needs_review, not stored, not a reason -> question with an unreadable part rendered unmarked, sent to solver.
- D3 (low, api.py:119-122): same-id join keeps first part's `cut`, drops continued_pages -> resolved split declined as cut_unresolved; second part's `cut` lost.
- D4 (low, refine.py:357-360): phase-40 40.4 "stored copy `incomplete`" not written (design drift; render computes it).
- D5 (medium, pdf.py:316,324): header/footer/page-number lines joined into the stem/option crossing a page break; no furniture filter.
- D6 (low, refine.py:95, cli.py:418-420): trace rows lack page and image hash; cannot map replies to pages or reuse them.
- Info: phase-40 risk "solve cache key" is moot: no cache in src/.
Nova

## Coordinator decisions
1. Accepted as designed. D2 (unreadable stored as a reason) and D3 (same-id join keeps cut/continued_pages) move into TASK-045 (43.2) because TASK-040 is already tested and under verification; both are small and tier 0.
2. Order: TASK-040 (verify, real run done) -> TASK-042/REQ-0046 (picture sources) -> TASK-044 (43.1 text-path boundaries) -> TASK-045 (43.2 + D2, D3) -> TASK-046 (measurement) -> TASK-047 (43.3 cut detector, 43.4 bounded recovery, 43.5 page cache) -> TASK-048 (43.6 sidecar + 43.7 prompt lines). Paid steps (real vision re-runs, about 3000 scanned questions about $16) only with the user go and a cost estimate; the cheap DGNL subset check in TASK-047 is within the earlier go only if under $0.3, otherwise ask.
3. The 99.9% targets are measured with Wilson intervals, never claimed.
