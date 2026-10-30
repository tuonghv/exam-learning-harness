# Phase 27 report: real ĐGNL ĐHQG-HCM 2026 sample exam, math slice (REQ-0032, TASK-027)

## Result
- PDF: 22 pages, 120 questions (language 60, math 30, science 30), no answer key. Free ingest: native text loses math symbols and tables, finds 0 segmented questions, and the math pages are not flagged for `ingest-refine`, so refine picks none.
- Workaround: I transcribed 10 math questions (PDF pages 14-15; exam no. 61-65, 67-71; no. 66 skipped, it needs the cable diagram) into `work/dgnl-real/exam-math.md` (untracked, copyright) and ran the unchanged `solve --real` (v1.2.0): 4 calls, $0.166, status `uncertain` for all 10 because there is no key.
- Engine answers by exam no.: 61 B, 62 C, 63 C, 64 D, 65 A, 67 A, 68 C, 69 A, 70 B, 71 B. My hand computation gives the same 10 (63 uses end-of-month deposits: 19.975 M; 64: m=1, n=3; 71: -7+2).
- n=10, one section, transcription by me, not the engine. Agreement is not an accuracy figure.

## Findings
- Gap: no path from a real PDF to the solver for math pages. The extractor needs a way to select math pages for vision refine and to feed `refined` questions to `to_exam_text` (today it ignores them).
- Not done: language (60) and science (30) parts, and the diagram question 66.
