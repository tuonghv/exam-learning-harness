# Phase 47: whole-question window extraction (TASK-047; REQ-0051)
# Draft: Phase 47 - whole-question window extraction (TASK-047, REQ-0051 AC1-AC4; RAW-00146/00154/00155)
Supersedes: phase-43 §43.4 option A (re-run) as primary recovery -> window call (Coordinator decision RAW-00154); 43.3, 43.5 kept.
## Premise (facts at HEAD d78ca86)
- refine loop: one call per page `_ask(llm, n, png, originals)` refine.py:220, loop :317-368; cut question kept as fragment + `cut`, next page `continues` merged by `_attach` :265 (bridge); orphans :336.
- `claude.run_claude_images(text, images=[(mime, bytes)...])` claude.py:53 already takes a list; cap 5 MB per image (:46,:64). make_real_llm sends 1 image (refine.py:93).
- `ReplyCache(dir)` .get/.put(namespace, key) replycache.py:13 (memory always, disk with dir). Not used by refine yet.
- pdf._extract has per-page lines after furniture strip at pdf.py:362 (`page_lines[i]` = page i+1): detector hook point.
- refcheck.incomplete_reasons(q, last_on_page=True) refcheck.py:106 gives options_incomplete / trailing_operator / formula_unbalanced: reused as the reply-side cut test.
- refined.json has no closed schema (consumers: api.py:125, inspect.py:54, extract_eval.py:295): optional fields are safe.
- Cost (TASK-040 traces): $0.024-0.072 per 1-image call, mean ~$0.04; most is fixed CLI overhead + output, one extra page image ~1.6k input tokens (~$0.005).
- F5 false alarm 8/25 (phase-46): text route cannot link a next-page figure; vision oracle `gold_pdf.vision_replies` :211 always writes `figures: []` (oracle artifact).
## Design
### 47.1 Cut detector (owner: pdf._extract after :362, new `_cut_boundaries(pages, page_lines) -> [warning]`) - AC1
- Per boundary n|n+1, both pages with native text (chars > 0, status != ocr): S1 last numbered line of n (segment._Q) has < 4 option lines after it and line 1 of n+1 is not numbered; S2 last line of n ends without `. ? ! :` or with an operator (refcheck._TRAIL); S3 line 1 of n+1 unnumbered; S4 page n+1 has an image block above its first numbered line and n ends inside a question.
- S1 or (S2 and S3) or S4 -> warning `{"code": "page_cut_suspect", "page": n, "message": "boundary n|n+1 (S1,S4)"}`.
- refine.FLAG_CODES += page_cut_suspect; pick_pages :55 adds page n and n+1 for it. Never removes a page; `--all-pages` unchanged.
- Scanned / OCR pages: no warning; the reply-side test (47.2) decides alone.
### 47.2 Cut test on the reply (owner: refine, new `_is_cut(q, items, suspect) -> bool`)
- True when q is the last numbered item of the page reply and any of: `cut` true; 0 < options < 4; no options while other items of the page have A-D; incomplete_reasons(q, last_on_page=True) has trailing_operator or formula_unbalanced; `suspect` (boundary n|n+1 flagged by 47.1).
- Deterministic, $0. A normal page: False -> no window, call count unchanged.
### 47.3 Window extraction (owner: refine.refine loop :317, new `_window_take(obj, pending, done_ids) -> (whole, rest, why)`) - AC2
- Page n reply, `_is_cut(last)` and n+1 in doc: drop `last` from page n items, keep it as `pending = {q, start: n, imgs: [png_n]}`.
- Call for n+1 = window: images [png_start .. png_n+1] in page order, prompt tail (47.5) names pages and the open id. It REPLACES the single call for n+1 (one call, one extra image).
- Accept: reply entry with norm_id == pending id -> question with page=start, continued_pages=[start+1..n+1], `window: [start..n+1]`, cut false. Other entries = questions of the last page (normal path: carry, part, similarity, gaps).
- Still cut (whole entry `cut` true and no other numbered entry) -> keep pending, next call window of 3 [start..n+2]. Never more than K=3 pages per window.
- Beyond K: take the last window's text as owner with `cut` true, next page single call -> `continues` bridge `_attach` (existing fallback, unchanged).
- Fallbacks (fragment never lost): window call fails (call_failed/invalid_reply after MAX_ATTEMPTS), or reply lacks the open id, or similarity(whole, fragment) < 0.6 on the fragment part -> restore the fragment with `cut` true, re-ask n+1 as a single page (today's path, bridge attaches `continues`), record `windows[i].result = "fallback"` + warning `window_fallback`.
- Duplicate guard: entries whose id is in done_ids (page start..n ids already accepted) are dropped, warning `window_duplicate`; entries after the open one whose ids are not increasing -> needs_review.
- `continues` in a window reply: `_dedupe` against the whole question; leftover text is attached by `_attach` (bridge).
- Ids/ownership: printed number (norm_id) as today; page = start page; same shape as a bridged question, so api.py:125 join, refcheck cut_unresolved and inspect work unchanged.
### 47.4 Bounded recovery (owner: refine.refine) - AC2
- Forward: cut at n and n+1 not selected (not key page: check_key_pages) -> add n+1 inline as a window.
- Backward: `no_owner` orphan on m -> one re-run over sorted(pages | {m-1}) with the per-run cache (done pages $0); m is then a window [m-1, m].
- Caps: <= 2 extra pages per chain, <= 4 per run, inside max_cost; `owner_has_options` orphans not recovered. Warning `recovered_pages`; `--no-recover` = selected pages only (windows still run inside them).
### 47.5 Prompt + call path (owner: prompts/dev/ingest/refine.md, refine.build_prompt/_ask/make_real_llm)
- refine.md new rule 11 (~70 tokens): "When several images are attached (order given under Pages), the question named Open starts on image 1 and is cut: return it FIRST and WHOLE (text, options, figures joined over the images; `cut` true only if it runs past the last image). Then return only the questions whose number starts on the LAST image. Never repeat other questions of earlier images. `continues` and `carry` refer to the last image."
- build_prompt(n, window=None, open_id=None): single page unchanged ("Page: n"); window tail "Pages: 7, 8 (image 1 = page 7, image 2 = page 8)\nOpen question: 10".
- llm(prompt, png): png = bytes (single, unchanged) or tuple of bytes (window); make_real_llm wraps bytes as [bytes]. Each image keeps render_page's 5 MB cap (3 x 5 MB raw ~ 20 MB base64; risk below).
- prompt_sha256 (refine.py:370) changes with refine.md -> new cache keys. Dev channel only; main does the release copy if one exists.
### 47.6 Page cache + trace (owner: refine._ask, cli ingest-refine :415) - AC3
- ReplyCache namespace "page"; key = model + sha256(full prompt text) + ",".join(sha256(png) per image in order) (prompt text holds pages and open id, so a window never hits a single-page entry; mock b"" images differ by the page label in the prompt).
- Value = validated reply obj. Hit: 0 calls, $0. Memory always; `--cache DIR` with --real only; mock runs never read disk (ReplyCache(None)).
- refine(..., cache=None, trace=None, recover=True): _ask writes trace rows {ok, cls, cost_usd, text, reason, page, pages, png_sha256: [..], cached}; cli passes `trace` to refine instead of make_real_llm (param kept for compat).
- Cost cap: check `cost >= max_cost` before every call incl. windows/fallbacks; dry-run prints "pages P, windows planned W (native), calls <= (len(P)+W) x MAX_ATTEMPTS".
### 47.7 Schema (optional fields only)
- question: `window: [int]`; refined: `windows: [{"pages": [..], "id": "10", "result": "whole|still_cut|fallback"}]`, `recovered_pages: [int]`. Old refined.json/doc.json load and render unchanged (test).
### 47.8 Mock + oracle (owner: refine.mock_llm :106, gold_pdf.vision_replies :194)
- refine.mock_llm: JSON list = sequential (unchanged); JSON object = replies keyed by label "8" or "7-8" parsed from the prompt (call-order independent).
- gold_pdf.vision_replies(info, windows=False): windows=True returns the keyed object incl. "n-1-n" windows (open question whole from all its pages) and figure stand-ins in `figures` where drawn.
## Cost estimate (state as estimate; measure on the slice)
- Per call ~$0.04; window call ~$0.045-0.05 (one more image + re-output of one question); upper bound used: +$0.04 per window.
- 22-page exam, --all-pages, 0 cuts: 22 calls ~$0.88 (unchanged). With N cut boundaries: + N x ($0.005-0.04) -> 5 cuts ~$0.91-1.08. Fallback adds one single call ($0.04) per failed window.
- Without --all-pages: flagged + cut-suspect pages only (43.3: ~8-12 pages ~$0.3-0.5).
- Default `--max-cost-usd 1.0` stays; a 22-page exam with many cuts may need 1.2 (dry-run shows it).
## Unit tests (tier 0, write first; mock replies keyed by label; namedtuple C as test_ingest_refine.py)
1. stem split (F2 shape): page 1 last q cut -> window "1-2" returns it whole; result 1 entry, continued_pages [2], window [1,2], no `continues` merge, needs_review false.
2. options on next page (F3): 2 options on page 1 -> window; whole has A-D.
3. figure on next page (F5): native S4 -> window; whole has figures; incomplete_reasons [].
4. passage over 3 pages (F4): window "1-2" still cut -> window "1-3"; group of 3 keeps context; 4th page would exceed K -> bridge fallback test.
5. no cut: 3 pages, 3 calls, no window, refined has no `windows` (call count asserted).
6. failed window call: fragment restored with cut true, single re-ask of page 2, bridge attaches, `window_fallback`.
7. duplicate guard: window reply repeats an earlier page-1 id -> dropped once, `window_duplicate`.
8. missing open id in window reply -> fallback (as 6).
9. scanned (no native text, no warning): reply `cut` alone triggers the window; reply without cut and 4 options -> no window.
10. detector: S1, S2+S3, S4 fire; complete boundary and S2 alone do not; never removes a page.
11. cache: second refine run with same cache = 0 calls; changed template -> miss; window key != single key; mock never reads disk.
12. trace rows have page/pages/png_sha256/cached.
13. recovery: forward n+1 added; no_owner -> m-1 added via re-run; caps 2/chain 4/run; owner_has_options not recovered; key page never added.
14. old refined.json (no window fields) renders identically (golden).
15. cost cap reached before a window -> cost_cap error, as today.
## Verification
| Item | Command -> expected | Tier |
|---|---|---|
| 47.1-47.8 | `python3 -I -m unittest discover -s tests/unit` -> new tests pass, only known failures | 0 |
| F2-F4 mechanics | gen_families + gold_pdf windows=True oracle, refine --mock keyed, extract_eval -> boundary 25/25 each, repairs (bridged `continues` merges) 0 vs bridge run 8/8/6, incomplete_to_solver 0; F5 vision false_alarm 0/25 | 0 |
| Real slice | `ingest-refine DGNL --pages 7-8 --real --max-cost-usd 0.15` and `--pages 14-15` -> q10, q66 whole with window [7,8]/[14,15], 0 orphans, 0 bridge merges; ~$0.09 each, ~$0.2 total (user-approved small check) | paid |
| Compare | tester script in work/TASK-047: fold-text difflib vs work/TASK-040/real/{7-8,14-15}.json and TASK-039 indep reads -> window >= bridge ratio for 10, 66 and neighbours; numbers only, no exam text | 0 |
| AC4 subset | dry-run first (cost shown); real `--pages 5-16` without --all-pages -> 0 orphans; ask user if estimate > $0.3 | paid |
## Decisions (options)
- A window call (chosen): whole question read as one unit, cost only one extra image, removes repairs. B bridge only (today: stitching, orphans 10/66 class, repeated debug, user rejected). C full re-extract of the neighbour page after the fact (pays page n+1 twice, still stitches): rejected.
- Bridge kept as fallback beyond K=3 or on failed window (REQ-0051 text).
## Risks
- Model returns page-n questions again -> duplicate guard (test 7). Wrong image order -> order stated in prompt + open id + increasing-id check.
- 3 large images: request ~20 MB base64; if the CLI rejects, lower zoom for windows (render_page already steps zoom) - check on the real slice.
- False positive cut (S2+S3 on prose): +$0.005-0.04 per page, no accuracy loss.
## F5 false alarm
- Vision: window (S4) or the bridge attaches the figure; the 8/25 is the oracle writing figures [] (fix in 47.8). Text route: unchanged by windows; needs a rule tweak (figure first on next page -> shared_figure for the last question). Recommend a separate small REQ, not TASK-047.
## exam-extraction skill text (main writes)
- "A cut last question is never stitched by hand: it is re-read whole by one call with the page images it spans (window <= 3). `continues` bridge is the fallback only; a `window_fallback` warning means re-check that question."
## Out of scope
- Text-route F5 rule tweak; windows over DOCX; > 3-page windows.
## Defects
- D1 (low, gold_pdf.py:211): vision oracle always writes `figures: []`, so F5 vision false alarm 8/25 measures the oracle, not the engine.
- D2 (low, refine.py:318): cost cap checked only before a page; with windows/fallback the check must run before every call (covered in 47.6).
Nova

## Coordinator decisions
1. Accepted. The F5 false alarm on the vision path is a mock artefact (gold_pdf.vision_replies writes `figures: []`, D1): fix the mock in this task; the text-path rule tweak becomes its own small REQ.
2. Paid slice (pages 7-8 and 14-15, about $0.2, user approved small real checks): dry-run first; anything above $0.3 asks the user.
3. Order (user priority RAW-00156): TASK-052 (human review path) runs BEFORE the build of this task; TASK-047 is held after its design is installed and resumes after TASK-052.
