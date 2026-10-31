# Report phase 44: text-path boundaries (TASK-044; REQ-0048)

Verdict: adopted. The PDF/DOCX text route no longer joins page furniture into questions, and a group passage intro or part heading after option D no longer lands inside option D.

## What changed
- `pdf.py`: page-number lines and repeated header/footer lines (first or last 2 lines of a page, repeated on at least max(3, half) pages; page-number patterns include `Page n of m`) are removed from the joined lines, with the info warning `page_furniture_removed` (count).
- `segment.py`: a group passage intro (Vietnamese "câu hỏi từ N đến M", "câu từ N đến M", "Dựa vào", English "Read the passage", line-start anchored) or a part heading after the options opens a pending context attached to the next question and repeated for its group; wrapped option lines still join. DOCX shares `segment`.

## Real evidence (DGNL native text, read-only, printed numbers/counts only; work/TASK-044/evidence)
An independent classifier by the tester put every changed line into a class: 19 removed lines are bare page numbers 1..19, each the first line of pages 4-22; of 158 question blocks 126 unchanged, 18 lose a page-number token, 14 have the passage moved out of option D, 0 unexplained; no stem or option word deleted (the render shows 85 positions changed because moved passages are repeated per group). All other fixtures render identically to base. The Vietnamese intro form "câu từ N đến M" appears 16 times in DGNL and already matched before the fix; the other new forms have 0 hits there.

## Tests
707 tests, only the 3 known failures (identical at base); 35 new boundary tests (the tester added 23 adversarial ones; the tests for the tester's D1-D3 fail on the base code); 4 mutations caught (filter anywhere on the page, page threshold ignored, pending context not reset between groups, passage still glued to D); 0 old assertions removed; no schema/solver/prompt change.

## Limits
- `n | Title` page-number pattern deliberately not added ("2 | 4" can be real math); a bare number that is the first/last line on at least half the pages is dropped by design.
- `segment._PART` duplicates `refine.PART_RE` (import cycle); a test guards drift (agree on 56 headings).
- The vision route is unchanged; the refine prompt rule on running headers comes with TASK-048.

User instructions honoured: RAW-00146, RAW-00133 (quality), RAW-00142 (short roles).
