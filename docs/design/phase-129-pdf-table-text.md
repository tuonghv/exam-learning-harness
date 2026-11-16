# Phase 129 – PDF free text path keeps table blocks (TASK-129, REQ-0136)

## Finding (approved paid run, RAW-00349)
DGNL 2025 Science from the free text path: 19/30 correct, 8 declined. The PDF adapter feeds only `paragraph` blocks to
segmentation (pdf.py page_lines loop; parts.py select_pages the same), so table blocks vanish: the boxed passage of
questions 118-120 (p19, a 1-column bordered box read as a table) and the data tables of p16 (population) and p18
(lighting). The refined path is not affected (vision reads the page).

## Plan modes
PDF ingest (full and `--pages`) only; DOCX keeps its own line source (tables not in lines), image/MD unchanged. No
prompt, cache key or solver change. Exam text of PDFs with tables gains the table text.

## Design
- 129.1 `segment.table_lines(text) -> [str]`: rows = `text.split("\n")`, cells = stripped `|` parts without empty
  ones; rows with no cell dropped. If every row has at most one cell (a box), return the cells as plain lines
  (a passage); else return `"| " + " | ".join(cells) + " |"` per row (the leading `|` never matches a question,
  option or heading rule).
- 129.2 pdf.py page_lines: `elif kind == "table": page_lines[-1].extend(segment.table_lines(text))`.
- 129.3 parts.select_pages: for a PDF source, `table` blocks give the same lines.

## Verification ($0)
Synthetic PDF tests (box passage -> group context; data rows not questions/options); real-input oracle: the 3
DGNL/DHQG PDFs keep 120 questions, exam-text diff shows only added table text; `--fast` NEW 0.
