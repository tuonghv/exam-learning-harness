---
id: EPIC-005
title: Document ingestion: PDF (primary), DOCX, Markdown to one canonical document, then the existing engine
source: [RAW-00049, RAW-00051, RAW-00055, RAW-00060]
created: 2026-10-29 14:04
updated: 2026-10-31 10:22
---
## Original (verbatim, never edit)
> **[RAW-00049]** 2026-10-29 14:04
> please standard input exam: tmp/input-exam-format.md
> **[RAW-00051]** 2026-10-29 14:10
> please standard input exam images too : tmp/input-exam-images-format.md
> **[RAW-00055]** 2026-10-29 14:36
> approve all do it fore me, if you need to run command just let me know, but we should document setup
> **[RAW-00060]** 2026-10-29 15:09
> you should build engine to inspect file ouput work/ingest-trial/out.md, as and this kind of json the best options for you, is it best choice tool free is it

## Goal
One ingestion boundary, not a second engine: `tmp/input-exam-format.md` (spec, read-only) asks for PDF (PyMuPDF, native text first, Tesseract OCR fallback, page/bbox traceability, image crops), DOCX (python-docx) and Markdown adapters that all produce one versioned, validated canonical JSON document, converted to the existing exam file format and passed to the current `solve` with minimal change. No subject logic, no new agent, backward compatible.


## Decomposition
<!-- One line per child: "- REQ-0012" (auto-added) or "- [ ] TBD: <coarse item not yet specified>". TBD lines are tracked until converted into REQs. -->
- REQ-0016
- REQ-0017
- REQ-0018
- REQ-0019
- REQ-0020
- REQ-0021
- REQ-0041
- REQ-0043
- REQ-0044
- REQ-0045
- REQ-0046
- REQ-0048
- REQ-0049
- REQ-0050
- REQ-0051
- REQ-0052

## Notes
Conflict to settle: CLAUDE.md says Python stdlib only; the spec names pymupdf, pymupdf4llm, python-docx (not installed here; tesseract and pdftotext are). See open questions on the first REQ.

## Progress log
- 2026-10-29 14:10 linked RAW-00051 (new input from user; re-check scope)
- 2026-10-29 14:36 linked RAW-00055 (new input from user; re-check scope)
- 2026-10-29 15:09 linked RAW-00060 (new input from user; re-check scope)
