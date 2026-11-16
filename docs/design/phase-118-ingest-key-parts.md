# Phase 118 – Fix-H parts: answer-key detection and page selection (TASK-118, REQ-0125)

Source rows: docs/design/phase-117-review-triage-b3.md (117-F001, F009, F010, F002, F003); designer draft work/TASK-118/handoff/design.md; repros work/TASK-117/repro_api.py.

## Goal
Answer-key heading found anywhere on a page (heading-like first line only), no flip on sentences, MD key refused with
`answer_key_present`, key guard kept under `--pages`, DOCX list/heading lines kept when `--pages` re-segments.

## Constraints
- Never-break: no key text in eval inputs; errors go to loud refusal, never to a silent leak.
- Files: `src/exam_engine/ingest/parts.py`, `src/exam_engine/ingest/api.py:70`. No prompt or cached body touched: no cache key.
- `boundary.py:39` reuses `parts._KEY` (line test); unchanged.

## Generality
All formats (PDF/DOCX/MD/image); no new literals (`_KEY` unchanged); the guard uses type, case ratio, length, `?` only.

## Known incidents
none (117-F001/F009/F010/F002/F003 are review findings).

## Plan modes
- PDF ingest: guard scans more blocks; 4 real PDFs proven unchanged (oracle below). `--pages` on PDF: 118.3 only.
- DOCX ingest: one page, so a key anywhere makes the whole doc `answer_key` (export refuses; coordinator decision).
- MD ingest: no `parts` set (api.py:44); `has_key` falls back to `find_parts`; 118.2 fixes the message path.
- Image/sequence: blocks are image + paragraph; same guard; no change on real inputs.
- refine/inspect/cli (`refine.py:95`, `inspect.py:91`, `cli.py:302`): read the same `find_parts`; they follow 118.1.
- solve/export/verify of finished runs: not affected (no re-ingest).

## Design
### 118.1 One key guard, all blocks, two tiers (F001 + F009; owner parts.py:9-17)
- `_key_heading(blk, head)`: `ln` = first line of `blk["text"]`, stripped; false unless `ln`, `"?" not in ln` and
  `_KEY.match(fold(ln))`. Then:
  - `heading_like` = `blk.get("type") == "heading"` or `segment._mostly_upper(ln)` or `len(ln) <= 40`.
  - head tier (block index < `_HEAD_BLOCKS` = 6, as today): true unless `ln` reads as a sentence, i.e.
    `not heading_like and ln.endswith(".")`. Keeps today's catch of a long mixed-case title such as
    `Đáp án và hướng dẫn chấm đề thi môn Toán` (coordinator: a missed key leaks, a false flip only refuses loudly).
  - deep tier (index >= 6): `heading_like` only (new scan, so the strict guard).
- `_starts_key(page) = any(_key_heading(b, i < _HEAD_BLOCKS) for i, b in enumerate(page["blocks"]))`.
- Real headings: `HƯỚNG DẪN GIẢI` (math p5 b1) yes; `ĐÁP ÁN`, `Answer key`, `Đáp án đề 01`, the test_ingest_inspect.py
  list (`Lời giải chi tiết`, `Solution 1`, `Marking scheme` ...) yes. `Solutions to climate change require money.`
  (42, mixed, ends `.`) no; `Lời giải thích nào sau đây đúng?` no.
- `Lời giải: Ta có:` (<= 40) passes by intent: worked-solution text means key content (never-leak direction). In the
  real inputs every `_KEY`-prefixed block sits on math p5-p12, already key pages (reach_parts.out).
- Tests (fail on old): 7 `Câu i` blocks + `ĐÁP ÁN` + `1.A 2.B` on one page -> `[{answer_key,[1,1]}]`; p2 first block
  `Solutions to climate change require money.` -> all exam; p2 `Lời giải thích nào sau đây đúng?` -> all exam.
  Guard (passes old and new): p2 first block `Đáp án và hướng dẫn chấm đề thi môn Toán` -> p2 answer_key.
  Update test_ingest_inspect.py:140-141 (`late` now `["exam","answer_key"]`): the old assertion encodes F001.
- Risk: a short (<= 40) statement starting with a key word, or a long one without a final `.` in the head blocks,
  flips the rest to key: loud `answer_key_present`, workaround `--pages`.

### 118.2 MD refusal message (F010; owner api.py:70)
- `doc["parts"]` -> `(doc.get("parts") or parts.find_parts(doc))` in the message join. Minimal: one expression, same
  fallback as `has_key` (parts.py:38); `_finish` unchanged.
- Test (fails on old): to_exam_text(MD doc, one `heading` block `Đáp án đề 01`) -> IngestError code `answer_key_present`,
  message has `1-1` (old: KeyError 'parts').
- Risk: none; must ship with 118.1 (after it, any MD with a key heading anywhere reaches this line).

### 118.3 Key guard under --pages (F002; owner parts.py:20-26, 104)
- `find_parts(doc, key_pages=())`: `in_key = in_key or page["n"] in key_pages or _starts_key(page)`.
  select_pages computes `key_pages` from the input doc before the copy: page numbers of every `answer_key` part of
  `doc.get("parts") or find_parts(doc)`; line 104 -> `find_parts(new, key_pages)`.
- Minimal: one optional arg, default keeps every other caller byte-identical; key state comes from the full document.
- Test (fails on old): repro F002 (p1 `Câu 1: x`, p2 `ĐÁP ÁN`, p3 `1.A 2.B`; select_pages "3") -> parts
  `[{answer_key,[3,3]}]`, has_key True (old: exam, False). Also select_pages "1" -> `[{exam,[1,1]}]`.
- Risk: none for exam-only selections (`key_pages` empty or outside the kept pages).

### 118.4 DOCX list/heading lines on re-segment (F003; owner parts.py:82)
- `b["type"] == "paragraph"` -> `b["type"] in ("paragraph", "list", "heading")`: the same lines the DOCX adapter feeds
  segment (docx.py:181-188 every `w:p`; tables are not in `lines`, docx.py:191-196).
- Minimal: one condition; PDF blocks are paragraph/table/image only, image adapter image/paragraph, MD skipped (:77).
- Test (fails on old): repro F003 (DOCX page: `Câu 1: x`, 4 `list` blocks `A. 1`..`D. 1`, paragraph `Câu 2: y` + 4
  options; select_pages "1") -> option counts `[4, 4]` (old `[0, 4]`).
- Risk: a DOCX Heading-styled `PHẦN ...` line now reaches segment as in the full ingest (intended parity).

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| False key flip (118.1 risk b) | to_exam_text refuses | `answer_key_present` with page range |
| `--pages` inside key part | refuses (118.3) | `answer_key_present`, use exam pages |

## Verification ($0)
| Item | Command -> expected |
|---|---|
| 118.1-118.4 | `python3 -I tools/run_tests.py --fast` -> NEW 0; the 6 new asserts fail on HEAD (stash check by tester) |
| Parts of 4 PDFs | re-run work/TASK-117/reach_parts.out's method (ingest each `input/` PDF, print `parts`) old vs new -> identical 4 lines (reach_parts.out:1-4) |
| Segment oracle | `python3 -I work/TASK-114/evidence/oracle.py` old (HEAD worktree) vs new -> identical output |

## Decisions
- Two-tier guard (coordinator): head blocks keep today's prefix match minus `?` and long sentences ending `.`; deep blocks need a heading-like first line. No colon tightening (leak risk).
- One-page DOCX/MD with a key -> whole doc `answer_key` (coordinator, phase-117 l.41); page cut at the key block = P3.
- F002 via `key_pages` from the full doc, not by keeping extra pages.

## Out of scope
Cutting a page at the key block; `BẢNG ĐÁP ÁN`-style headings not starting with a key word (`_KEY.match` is a prefix match).

## Defects
- D1 (low, tests/unit/test_ingest_inspect.py:140-141): asserts the F001 bug (`late` heading -> exam); must be flipped in 118.1.
