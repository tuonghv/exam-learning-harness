# Phase 44: text-path boundaries, page furniture and passage after option D (TASK-044; REQ-0045)
Source: docs/design/phase-43-question-completeness-gate.md section 43.1 (gap table rows "headers/footers/page numbers inside a question", "section/subject headings", "shared passages", defects D1 and D5). Text copied from 43.1:

### 43.1 Text-path boundary fixes (owner: segment.segment, pdf._extract) - tier 0, $0
- Furniture filter in pdf.py before :324: drop from `all_lines` (blocks untouched) lines among the first/last 2 of a page whose digit-folded form repeats on >= max(3, half) pages, or that match a page-number pattern (`Trang/Page n[/m]`, `- n -`); info `page_furniture_removed` (count).
- segment.py:28: an unnumbered line after options that matches api.GROUP_RE (move to segment, api imports) or a part heading (parts.split_part) is NOT glued to D: it opens `pending_context`, attached as `context` of the next question; `_share_context` repeats it. Wrapped options keep today's join.
- Options: A furniture+GROUP only (chosen, deterministic, fixes D1/D5). B prompt the vision model for every page ($0.9/exam, text path stays wrong). C drop all repeated lines anywhere (deletes real repeated stems).
- Risk: a repeated real line at page top (e.g. instruction) -> only first/last 2 lines + >= 3 pages; test.
 (owner: refcheck.incomplete_reasons) - tier 0, $0

## Plan modes
Affects the PDF/DOCX text route (ingest without vision refine). The vision route (`ingest-refine`) and `--refined` exam rendering are unchanged. Old doc.json files load; their rendered exam text changes only where page furniture or a passage heading sat after option D (golden diff required).

## Tests-first list (tier 0, synthetic placeholder text)
1. page number lines (`Trang 3/22`, `- 3 -`, `Page 3`) at page top/bottom removed from the joined lines; stems and options untouched.
2. a repeated header on >= max(3, half) pages (first/last 2 lines, digit-folded) removed; a repeated real stem line in the middle of a page kept; a repeated line on only 2 pages kept.
3. a group passage intro (GROUP_RE, e.g. "Questions 46-52 ..."/"Dua vao ...") or a part heading after option D opens a pending context for the next question and is NOT glued to option D; wrapped option lines still join.
4. context repeated to every question of its group (`_share_context`), later questions keep the passage.
5. golden: render every exam under examples/, evals/, tests fixtures and work/dgnl-real/doc.json before/after: unchanged except documented diffs (list them by printed number only).
6. info warning `page_furniture_removed` with the count; no warning when nothing removed.
7. DOCX path (`segment` shared) behaves the same for the passage-after-D case.
## Verification
Tier 0: unit suite; golden diff; independent oracle by the tester on generated page sets. Real check on the DGNL text path (doc.json native text) read-only: count of removed furniture lines and the changed questions by printed number.
## Risks / out of scope
A real repeated line at a page top could be removed (only first/last 2 lines and >= 3 pages); the vision route; refine prompt changes (TASK-048).
