PROGRESS: COMPLETE
SKILLS: verify, crosscheck, token-efficiency (security pass by hand on the diff; verify-phase)

Tier: 0 static + suite evidence. No paid run, no Bash (UNVERIFIED items name the command).

## Claims
- Suite: VERIFIED. evidence/suite-final.txt: Ran 1072, failures=3 errors=1 skipped=35 xfail=2; the 5 FAIL/ERROR names equal baseline-failures.txt:1-5 and head-failures.txt (lxml docx textbox, check_examples x2 incl. dgnl pairing, cwd_independence). No new failure. (suite-final.txt and baseline-failures.txt have no `# rc` header; rc taken from "FAILED" line. t47-suite2.txt header rc 1, head 8f32be8+dirty = older tree.)
- 47.1 detector warnings only: VERIFIED by code. pdf.py:193-224 emits level=info warnings, removes nothing. Tester golden (test.md:19, test_window_golden) asserts byte-identical output when no cut, and only added `page_cut_suspect` info warnings on DGNL (6+, acceptable per brief). Note: FLAG_CODES now includes page_cut_suspect (refine.py:25), so a default (no --all-pages) selection gains flagged page n, as designed. Design 47.1 says pick_pages adds n AND n+1; code adds n only, n+1 comes by window/forward recovery (refine.py:568-575). Deviation low, behaviour equivalent under recover.
- 47.3 whole-question window: VERIFIED by code + mock tests. refine.py:444-513 sends images [start..n] in one call, accepts entry with the open id, sets page=start, continued_pages, window, drops cut; fallback to bridge on call_failed/invalid_reply/missing id/similarity<min (459-466); duplicate guard 477-491; K=3 at 565. Tests 1-9 mapped in test.md:9, pass in suite.
- 47.4 recovery caps: VERIFIED. forward: extra<CHAIN_EXTRA(2) and len(recovered)<RUN_EXTRA(4) and _extra_ok (key pages excluded) refine.py:571-575; backward capped RUN_EXTRA-len(recovered) at :593, re-run recover=False, no recursion (_recovered==()) :594-597, owner_has_options not recovered (kind=="no_owner" only :591). Mutations of each cap killed (test.md:28).
- Cost cap before every call: VERIFIED. refine.py:423 `cost >= max_cost` in ask() before windows, fallbacks, re-run (re-run gets max_cost-cost :596). Raised cost_cap not swallowed (:449-450). Limit: checks spent cost, not spent+estimate, so one call may exceed the cap by one call (as before).
- 47.6 cache key + trace: VERIFIED. refine.py:277 key = model, sha256(prompt incl. pages/open id), sha256 of each png in order; trace row fields page,pages,png_sha256,ok,cls,cost_usd,text,reason,cached :278-289. Disk cache only with --real (cli.py:695); mock = ReplyCache(None). Mutations (key w/o model/prompt) killed.
- Flags: VERIFIED by code cli.py:635-639,693-695 (--no-recover, --no-window, --cache). Behavioural effect covered by unit tests (test.md:9,13).
- Dry-run line / EST_CALL_USD: VERIFIED as an estimate. cli.py:672-677 prints pages, windows planned (native only), calls <=, cap, est cost; refine.py:28-30 labels 0.08 an ESTIMATE. Measured: mean 0.036, max 0.045 single page (test.md:31, work/dgnl-real/v3 traces, not re-run by me); window cost UNMEASURED. 0.08 ~2.2x mean so dry-run overstates; design 47.x text uses ~$0.04/call (22 pages ~$0.88) while dry-run would print $1.76 for 22 pages (> default cap 1.0): inconsistent, see D2.
- REQ-0045 AC2 (design of remaining gaps, cost per exam stated, reuse first, hybrid Python-first): VERIFIED. Design "Cost estimate" states per-exam cost ($0.88 / 5 cuts $0.91-1.08 / subset $0.3-0.5); reuse: ReplyCache shared with boundary.py (replycache.py:1-7), _attach bridge as fallback, render_page cap reused; detector and cut test are Python/$0, AI only on suspected cuts.
- Oracle F2-F4 mechanics: VERIFIED via unit test test_completeness_measure_pdf.test_window_oracle_whole_questions_no_orphans (25 q, 0 orphans; fails when window disabled; test.md:24-25). I did not re-run it (no Bash).
- Design test 10 "never removes a page": UNVERIFIED by test (no assertion, test.md:37); by code pick_pages only gains a flag code, removes nothing.

## NOT RUN (paid, need user go; registered question pending)
- Real slice `ingest-refine DGNL --pages 7-8 --real --max-cost-usd 0.15` and `--pages 14-15` (q10, q66 whole, 0 orphans, window cost measurement).
- AC4 subset `--pages 5-16` real without --all-pages (0 orphans), after dry-run.
- Compare vs work/TASK-040/real difflib: depends on the real runs.
- State stays unverified for real behaviour until these run.

## Security pass (git diff 2cc9808..HEAD ingest + cli.py), by reading
- Cache dir: --cache DIR user-supplied; file name = namespace + sha256 hex (replycache.py:18-20), no key text in path, no traversal; write errors swallowed; corrupt file = miss. OK. Residual (D1): a valid-JSON but wrong-shape cache file (e.g. a list, no "questions") is returned unvalidated (refine.py:279-283, replycache.py:28-33) -> TypeError/KeyError at refine.py:452, caught only as OSError/ValueError at cli.py:706 -> traceback. Local self-inflicted, low.
- Trace: rows hold raw model text + sha + cost; no keys/env/args. Written to OUT.trace.json beside --out (cli.py:712-714), contains exam content as does --out; keep out of git (already a work/ output). Written in `finally` even on error: OK.
- Prompt injection: window prompt contains only fixed template, page numbers (ints) and open id from norm_id (digits only, refine.py:153-157). No page text enters the prompt (images only). Image content is model-visible as before; reply is schema-validated; the injected reply can only change question text, same as single page. OK.
- Image caps: each page <=5 MB (render_page :98-105, claude.py:64 per image); windows <= WINDOW_MAX=3 images (15 MB raw, no total cap). Low; document. Subprocess runs with tools off, empty cwd (refine.py:110).
- No new network, shell or eval use found.

## Defects
- D1 (low) src/exam_engine/ingest/refine.py:279-283 + replycache.py:28: cache hit returned without shape/validation check; wrong-shape file crashes with traceback. Fix: run validate_refined on hit, else miss.
- D2 (low) src/exam_engine/ingest/refine.py:30 vs docs/design/phase-47-whole-question-window.md "Cost estimate": estimate 0.08/call vs design 0.04/call; dry-run for a 22-page --all-pages exam shows ~$1.76 vs design ~$0.88. Align one number (measured mean 0.036) and state window cost as unmeasured until the real slice.
- D3 (info) cli.py:676 dry-run calls bound ignores recovery pages (up to +4) and fallback re-asks; advisory only.
- D4 (info, tester D1) DGNL ingest gains 6+ info page_cut_suspect warnings: accepted per brief.

## NEXT
- Main: ask user for the paid slice go (7-8, 14-15, then 5-16 after dry-run); decide D1/D2 fix or accept.
