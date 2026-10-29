PROGRESS: COMPLETE
SKILLS: verify, crosscheck, token-efficiency

# Verify TASK-014 (REQ-0020 AC1-AC5) - Argus

Judged by code reading plus work/TASK-014/evidence.md (323 tests OK; real PDF run) and trial-report.md:3,7. I did not re-run anything (no Bash). Unit-test counts are the coder's claim: UNVERIFIED by me.

| AC | Verdict | Evidence |
|---|---|---|
| AC1 | PASS | inspect.py:48-87 header lists source, status, pages, blocks/assets/warnings/suspicious, parts, questions, per-page status, then page-by-page blocks. cli.py:267-299 takes doc.json. trial-report.md:3-7. |
| AC2 | PASS with caveat | Detection: parts.py:9-34 (heading in first 3 blocks of a page, key sticks to the end). Notice: inspect.py:65-67. Trial parts "exam p1-4, answer_key p5-12" at trial-report.md:7. `--pages` handling: parts.py:56-88, api.py:35-36, cli.py:286-287. Guard: api.py:56-60, wired at cli.py:253. Caveat: the guard is on `ingest --exam-out` only. `solve` never calls ingest (cli.py greps: 247/253/289 only). It is refused if the solve input comes from `ingest --exam-out`. |
| AC3 | PASS | inspect.py:18-45 gives split_formula, option_without_text, stray_chars, numbering_gap, plus adapter warnings. Page and block id are reported (inspect.py:80-82). numbering_gap is document-level, with no page or block (inspect.py:83-85). That is acceptable. |
| AC4 | PASS | Read-only: report() only reads, select_pages deep-copies (parts.py:64). The `--out` file is written only when given (cli.py:291-293). inspect.py imports only re and parts. api.py imports only hashlib, os, adapters, parts, schema and parser (api.py:2-7), with no network or Claude call. Tests: tests/unit/test_ingest_inspect.py covers headings (132-149), page specs (151-177), the guard (179-189) and heuristics (201). |
| AC5 | PASS | inspect.py:8 and 86; test at test_ingest_inspect.py:199. |

## Key-leak guard analysis
- `--pages` covering key pages: select_pages recomputes parts (parts.py:87), so the key is still detected and refused (api.py:56). A bypass needs an explicit `--allow-key-pages`. OK.
- `--pages` that excludes the key: allowed, intended.
- Eval keys: nothing in the files read touches eval keys or eval dirs. The only "key" is the answer-key pages of the source document.

## Defects
- D1 (medium, heuristic limit) parts.py:12-17: the key is detected only if a heading matching `_KEY` is in the first 3 blocks of a page (test_ingest_inspect.py:139-143 pins this). A key whose first page has no heading, or whose heading is later than block 3 (e.g. after a header, page number and title), is not detected. Then has_key is False and to_exam_text does not refuse. The `\b` anchor only matches the start of the folded text. Suggest documenting it, or a fallback (e.g. a "dap an" heading within the first 5 blocks, or a repeated "Cau N: A/B" key table). No fix is needed for PASS because AC2 targets the headed trial doc.
- D2 (low) api.py:56 / parts.py:37-38: a doc.json with no "parts" key (hand-made or older) gives has_key False, and the guard is silent. Also Markdown sources never get parts (api.py:33), so there is no guard for them (a test at test_ingest_inspect.py:205 covers this). `ingest` always sets parts for non-md files, so this is only reachable via a hand-edited JSON or `to_exam_text` on an old doc. Consider calling find_parts when "parts" is absent.
- D3 (info) The guard is not in the `solve` command itself (see AC2 caveat). Confirm the design intends the guard on `ingest --exam-out` only.

## Unverified
- The 323-test run and the real-PDF refusal output are in evidence.md as the coder's summary without header/rc. If wanted, run `.claude/scripts/save-evidence.sh unit-all -- python3 -I -m unittest discover -s tests/unit` and `run-guard -- python3 -I exam.py ingest <pdf> --exam-out <tmp>` (expect rc 2 and answer_key_present).
