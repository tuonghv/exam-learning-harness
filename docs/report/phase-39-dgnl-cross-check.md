# Report phase 39: cross-check of the real DGNL 2026 solution against the PDF (TASK-039; REQ-0042)

Verdict: the engine's answers hold up where it answered; its failures are extraction failures at page breaks, not solving failures. No question text is quoted here; only printed numbers, pages and statuses.

## Method (no paid `claude -p` run)
PDF = examples/dgnl/De-thi-minh-hoa-2026-Final.pdf (22 pages, 120 questions, no key). Four verifier subagents solved each section from the PDF pages without opening any engine output; four more compared the engine's extracted exam files (e3-*.md) with the PDF pages; two adjudicators re-read the contested and doubtful items; the coordinator recomputed Q66 and the needs_review statistics. Evidence: work/TASK-039/evidence/*.txt, handoffs work/TASK-039/handoff/*.md (untracked).
Limit: the solvers are the same model family as the engine, so agreement is not accuracy and there is no official key. Only disagreements and flagged flaws carry information.

## Answers (engine `answers.json` vs independent reads)
| Section | Agree | Disagree (printed n) | Engine declined (printed n) |
|---|---|---|---|
| Vietnamese 1-30 | 26 | 8 | 10, 14, 23 |
| English 31-60 | 30 | - | - |
| Math 61-90 | 29 | - | 66 |
| Science 91-120 | 28 | 112, 120 | - |
Total 113 agree, 3 disagree, 4 declined. After a third reading: Q8 and Q120 stay with the engine (2 of 3 reads); Q112 is the one open disagreement (engine D, two reads A) and the question is flawed (A and D both true). Declined: 10 B, 23 B (alternatives defensible), 66 A (the coordinator recomputed the minimum spanning tree from the graph on PDF page 15: 100+120+140+160+260 = 780 = option A; `q66_kruskal_check.txt`), 14 is flawed (two correct options, one misspelt), so declining it was reasonable.

## Extraction (engine exam files vs PDF)
- English: cosmetic only (bold target words lost in 47, 49, 54, 55, 58; stems still name them).
- Math: only printed 66 wrong and it blocks the answer: the question sentence and the weighted graph are at the top of PDF page 15, the stem is on page 14; both missing in the extraction.
- Vietnamese: 10 and 23 block the answer (passage paragraphs lost at page breaks p.4-5 and p.6-7); 24 and 25 may change; 21, 22 cosmetic (paragraph 5 and attribution missing); 13 diacritic in one option.
- Science: clean (3 cosmetic items).
Pattern: all blocking defects are content that continues across a PDF page break; the engine declined 3 of the 4 affected questions instead of guessing (safe behaviour).

## needs_review as a signal (`needs_review_vs_extraction.txt`)
Flagged 6, 10, 66, 67, 89, 102. It caught 2 of the 3 blocking questions (10, 66), missed 23 and 24-25; 4 of 6 flags were clean (precision 2/6). The solver's own doubt marked 2 of the 3 contested answers (112, 120) as `medium` (13 medium overall), a useful weak signal.

## Flawed or ambiguous questions in the PDF itself (not engine defects)
Two defensible options or a misspelt option: 4, 14, 18, 24, 112, 114, 120 (and alternatives for 21, 23); 80 has only an empty set as correct answer; 63 depends on unstated deposit timing. Treat the official key as possibly different on these.

## Improvements, ranked by evidence
1. Page-break continuation in refine (stem sentence, figure, passage paragraphs): explains 10, 23, 66 and 21-25. REQ-0043 / TASK-040 (tier-0 tests; a paid re-extract of about 8 pages, about $0.3, needs the user's go).
2. Referenced-part check and an actionable extraction-suspect report (declines explained as missing text): the heuristic would have flagged 23. REQ-0044 / TASK-041 (tier 0).
3. REQ-0024 (solve gate): the evidence shows extraction errors do reach the solver, but the solver declined instead of guessing wrong, so the gate mostly saves cost; keep parked, revisit after 1 and 2.
4. Low: keep bold/underline markers (English 47-58) and a flawed-question flag in the report; the numeric-science letter mapping stays an open item.

## Limitations
No official key; same-family solvers; the independent reads of 8 questions disagree among themselves where the PDF is flawed; a fresh re-extract was not run (paid).

User instructions honoured: RAW-00143, RAW-00133 (quality), RAW-00142 (short roles).
