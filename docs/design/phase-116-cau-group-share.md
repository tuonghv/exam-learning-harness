# Phase 116 – Share an unaccented `Cau N - M` group passage (TASK-116, REQ-0123)

Follow-up of TASK-114 (114-F002). S = src/exam_engine/ingest/segment.py.

## Premise (corrected)
TASK-114's report said a `CÂU 31 - 35` passage reaches q31 only. Wrong: `api._share_context` (api.py:151) matches with
`segment.GROUP_ANY` = GROUP_RE + re.I (S:77), so `CÂU` is already shared. Checked 2026-11-16: `CÂU 2 - 3` -> q2, q3 both
get the context; `Cau 2 - 3` -> q2 only. The gap is the unaccented group word: GROUP_RE's `[Cc]âu` has no `Cau`.

## Plan modes
Both: segment/api run in the single-source and the pipeline ingest path. No solve-path, prompt or cache-key change.

## Design
### 116.1 GROUP_ANY from the intro span (owner: S `build`, S:13-35, S:77)
- Change: `build()` adds `GROUP_ANY=re.compile(span_i, re.I)` (span_i = the 114.2 span with `(?i:C[aâ]u...)`);
  S:77 becomes `GROUP_ANY = _NS.GROUP_ANY`. GROUP_RE, `_INTRO` untouched.
- Why minimal: reuses span_i; the langtable (`group` alternatives) keeps working because span_i is built from it.
- Test (fails today): segment + `api._share_context` over `[Câu 1 + ABCD, 'Cau 2 - 3: Doc doan van', 'Para.', Câu 2 + ABCD,
  Câu 3 + ABCD]` -> q2 and q3 context both start `Cau 2 - 3`. Guard: same with `CÂU 2 - 3` (passes today);
  `segment.GROUP_RE.pattern` unchanged (golden test).
- Risk: GROUP_ANY searches anywhere in a context; `cau 3-5` without diacritics mid-context now opens a range, like
  `câu 3-5` already does. Detected by the oracle.

## Verification ($0)
| Item | command -> expected |
|---|---|
| 116.1 | `python3 -I tools/run_tests.py --fast` -> NEW 0; new test fails on old src |
| oracle | work/TASK-114/evidence/oracle.py old vs new -> 0 segment changes (GROUP_ANY is not used by segment); plus a `_share_context` dump over the 4 input PDFs -> 0 changes or only Cau-range shares |

## Decisions
- Build GROUP_ANY in `build()` from span_i, not a string replace on GROUP_RE.pattern (fragile with a langtable).
