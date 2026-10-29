---
id: EPIC-005
title: Document ingestion: PDF (primary), DOCX, Markdown to one canonical document, then the existing engine
source: [RAW-00049, RAW-00051]
created: 2026-10-29 14:04
updated: 2026-10-29 14:10
---
## Original (verbatim, never edit)
> **[RAW-00049]** 2026-10-29 14:04
> please standard input exam: tmp/input-exam-format.md
> **[RAW-00051]** 2026-10-29 14:10
> please standard input exam images too : tmp/input-exam-images-format.md

## Goal
One ingestion boundary, not a second engine: `tmp/input-exam-format.md` (spec, read-only) asks for PDF (PyMuPDF, native text first, Tesseract OCR fallback, page/bbox traceability, image crops), DOCX (python-docx) and Markdown adapters that all produce one versioned, validated canonical JSON document, converted to the existing exam file format and passed to the current `solve` with minimal change. No subject logic, no new agent, backward compatible.


## Decomposition
<!-- One line per child: "- REQ-0012" (auto-added) or "- [ ] TBD: <coarse item not yet specified>". TBD lines are tracked until converted into REQs. -->
- REQ-0016
- REQ-0017
- REQ-0018
- REQ-0019

## Notes
Conflict to settle: CLAUDE.md says Python stdlib only; the spec names pymupdf, pymupdf4llm, python-docx (not installed here; tesseract and pdftotext are). See open questions on the first REQ.

## Progress log
- 2026-10-29 14:10 linked RAW-00051 (new input from user; re-check scope)
