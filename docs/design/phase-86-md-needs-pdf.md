PROGRESS: COMPLETE
SKILLS: design, token-efficiency
# Phase 86 - md-pdf-pairs (draft for docs/design/phase-86-<slug>.md)
## Goal
Every md in a report pack has a same-name pdf (and vice versa); registry says so; checker fails on a gap; reports/dgnl2026 rebuilt at $0: 10 md = 10 pdf.
## Plan modes
None affected: only report_pack, registry, checker; plans/ and solve output are not read or written differently.
## Design
86.1 Registry (config/report_kinds.json:4,19): add "pdf" to `ext` of answer-sheet (`["md","pdf"]`) and score-summary (`["md","pdf","json"]`); add top-level `"pdf_with_md": true`. Guide table docs/guide/report-kinds.md:14,19 Ext cells gain `pdf`; add one line under the intro: "rule `pdf_with_md`: every md has a pdf of the same name". test_85_1_doc_table_equals_registry stays the guard. New unit invariant: when `pdf_with_md`, every kind whose ext has md also has pdf (catches a future md-only kind).
86.2 Pack renders pdfs (report_pack.py:97 build_pack): when `pdf`: (a) before any write, `reporter.find_pdf_renderer()` is None -> `ValueError(reporter.NO_RENDERER-like "no PDF renderer found (Chrome, weasyprint, wkhtmltopdf); install one or use --no-pdf")` (AC6, no silent html); (b) after all md are written (after line 144), new `_pdf_siblings(out_dir, lang)`: for each file f with `rk.parse(f)`, ext md, kind ext has pdf, and no `<stem>.pdf` -> `reporter.md_to_pdf(md, pdf, lang=lang)`; `not ok` -> ValueError naming file and note. Replace lines 122-127 (combined report) by this same pass. write_reports/engine.run/`exam report` unchanged (Decision 1).
86.3 Pack self-check (report_pack.py:148): drop the html-stands-in clause; a pdf missing is `missing` (expected() already lists pdf via 86.1, pdf=False skips them).
86.4 Checker (tools/check_report_pack.py:110): drop html stand-in; new check after line 112 when `reg.get("pdf_with_md")`: `chk("md without pdf", 0, n)` and `chk("pdf without md", 0, n)` over parsed standard names (same stem). Kinds come from the registry only; no kind literal.
86.5 INDEX: no code change; write_index lists the new pdfs (count "-", kind description), totals rise by 5. report-index never enforces pairs, so legacy folders (report.md without pdf, answers.md) are untouched and still pass.
86.6 Rebuild (main, $0): `exam report-pack plans/dgnl2026f/out-{Vietnamese,English,Math,Science2} --out reports/dgnl2026 --exam dgnl2026 --run f --key input/dgnl/De-thi-minh-hoa-2026-Final.answer.txt`, then `python3 -I tools/check_report_pack.py reports/dgnl2026 plans/dgnl2026f/out-{...} --key <same> --expect-correct 113`. Expect: 35 files + INDEX (was 30); md 10, pdf 10 (4+1 solution-report, 4 answer-sheet, 1 score-summary); INDEX `- answer-sheet: 8`, `- score-summary: 3`, `- total: 35`; checker RESULT ok, 113/120.
86.7 Answer-sheet pdf readable: fenced grid -> `<pre><code>` (md2html.py:176-185, monospace font md2html.py:52). Check `pdftotext -layout` on one answer-sheet pdf shows "N Questions" and the circled letters column-aligned (U+24B6.. may fall back out of DejaVu Sans Mono).
## Unit tests (tests/unit/test_report_kinds.py)
- registry invariant (86.1); doc table equality still passes.
- build_pack with fake renderer (renderer/runner injectable or monkeypatch reporter.md_to_pdf): every md has a pdf, incl. answer-sheet and score-summary.
- build_pack pdf=True, find_pdf_renderer -> None: ValueError text contains "no PDF renderer"; no html left.
- md_to_pdf returns (False, note) for one md -> ValueError naming that file.
- checker: delete one answer-sheet pdf -> FAIL "md without pdf"; add orphan `<stem>.pdf` with no md -> FAIL "pdf without md"; complete pack -> ok.
- report-index on a legacy tree with report.md only: no failure, rows unchanged (existing 85_3 golden stays byte-identical).
- pdf=False pack: no pdf written, self-check passes (expected() skips pdf).
## Failure modes
| Failure | System response | Operator sees |
| no renderer | ValueError before writing | "no PDF renderer found (...)" exit != 0 |
| render fails for one md | ValueError | file name + md_to_pdf note |
| pdf deleted later | checker FAIL | `md without pdf 0 1 FAIL` |
## Decisions (best picks taken; the user's instruction RAW-00263 is "never miss a pdf", no contrary choice)
1. (A) new pdfs are made in the pack only (build_pack); engine.run / `exam report` keep one pdf.
2. (A) registry keeps ext lists and gets a `pdf_with_md` flag; the checker reads the flag.

## Risks
- Existing checker/pack test fixtures without answer-sheet/score-summary pdf will fail: coder updates fixtures (test_85_5_*, test_85_10_*).
- Rebuild needs Chrome; render time ~5 extra pdfs.
## Out of scope
Legacy folders, learning-report path (writes via write_reports, not in pack), html fallback for `exam report`.
## Defects
- D1 minor, report_pack.py:125-127 + checker:110: renderer failure today appends "PDF skipped" to md and passes via html stand-in, against AC6; fixed by 86.2/86.4.

Nova
