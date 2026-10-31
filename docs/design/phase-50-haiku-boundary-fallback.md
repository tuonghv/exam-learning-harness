# Phase 50: Haiku fallback for uncertain boundaries (TASK-050; REQ-0053)

# Draft: Phase 50 - AI boundary hints for uncertain lines (TASK-050, REQ-0053 AC1-AC5, RAW-00147/00148)
## Premise (facts, HEAD e6254a3 + dirty tree)
- One segmenter for all text routes: segment.segment(lines) segment.py:16, called by pdf.py:367 (after _strip_furniture :362), docx.py:213, parts.select_pages parts.py:80.
- Rules: _Q `Câu|Cau|Question N` or `N.`/`N)` (:4); _OPT A-D (:5); after options, _INTRO/_READ/_PART lines open `pending` context (:43), any other line is glued to the last option (:46). _PART = roman only (:13).
- Subject aliases: router.known_names/subject_key (router.py:14-27, config/subjects.json). Key pages: parts._KEY (parts.py:9).
- Text-only CLI call exists: claude.run_claude(prompt, model=, timeout_s=, cwd=) claude.py:49; JSON reply parse claude.extract_json :133; cost from envelope total_cost_usd :114.
- `ingest` has no --mock/--dry-run/--real/--max-cost-usd today (cli.py:225-242); refine/solve have them (same convention reused).
- No cache in src (grep = 0); 43.3 `page_cut_suspect` not in FLAG_CODES (refine.py:22): TASK-047 has not landed.
- 43 "Out of scope: AI boundary review per question" = review of EVERY question; this task reviews only rule-uncertain lines (user RAW-00147), so it supersedes that line narrowly.

## Goal
- An exam using an unseen question-start word (`Bài 3:`, `Item 3)`, `Q3.`; RAW-00148 first target), an unknown subject/section heading, or a passage after option D segments correctly when `--boundary-ai haiku` is on; a normal exam sends 0 windows ($0). Measured: windows, hints applied/rejected, cost per exam.

## Plan modes
- Default OFF: ingest output byte-identical (no new warnings). Mock/dry-run: tier 0. Real: only `--real`, cost-capped.
- Routes: native text PDF, OCR text, DOCX. NOT vision refine (see 50.7). MD (FORMAT.md) not affected.

## Design
### 50.1 Uncertainty signal (owner: new src/exam_engine/ingest/boundary.py `suspects(lines, page_of=None, known=None) -> [{line, kind, token}]`) - pure, $0
Lines before the first rule question, and from the first parts._KEY line on (answer key), never qualify. Priority order = send order:
- QS1 unknown start marker: no _Q match; matches `^\s*(\S{1,12}?)\s*(\d{1,3})\s*[.:)\]–-]\s*\S` with token not A-D, not `(`-wrapped (refcheck _MARKER), and number == expected (last rule/hinted n + 1). `token` = fold(token). Only the first 2 lines per token are sent (exemplars).
- QS2 stem without marker: an unnumbered, non-option line X such that the current question already has a complete A..D run and an `A.` option follows X within 4 non-empty lines (a second option run with no start). This is today's 43.2 merge_suspect shape, caught before merging.
- SH heading: line <= 60 chars, <= 8 words, no terminal `.?!,;`, >= 60% letters upper or every word capitalised, next non-empty line is a _Q/_INTRO match or QS1; not _PART, _INTRO, _READ, not a known subject alias (router.known_names), not _KEY. Catches `PHẦN 1: ...` (arabic) and unknown section titles.
- QE after option D: run complete (D present), D text ends with `.?!)` or <= 60 chars, the line starts upper/quote/digit, is >= 40 chars or ends with `:`, not _INTRO/_READ/_PART. Long unterminated D -> wrap, never a suspect.
- NB number break: _Q match whose n != expected and != 1 (weak start, e.g. a `2)` list in a stem).
- RC rule conflict: a line matched by two rules (_OPT and _Q, or _INTRO and _Q).
- PB page boundary: when 43.3 lands, `page_cut_suspect` pages -> last 6 lines of n + first 6 of n+1 (uses page_of). Until then not emitted.
- Thresholds keep normal exams at ~0: every rule needs the rule engine to have NO match plus a sequence/shape fact. Measured in V1; target <= 1 window per normal exam.
### 50.2 Windows (owner: boundary.windows(lines, suspects, span=8, max_lines=40, max_windows=12))
- Suspect line +-8 lines, overlapping spans merged, cut to 40 lines; id `w<k>`; text = `L<abs index>| <line>`.
- More than max_windows -> keep by priority, warning `boundary_ai_skipped` (count).
### 50.3 Prompt + call (owner: prompts/dev/ingest/boundary.md, boundary.build_prompt(windows), boundary.ask)
- Prompt (en instructions, vi+en examples, synthetic): classify listed lines; labels question_start, subject_start, section_start, question_end, passage, option_continuation, other; reply ONLY JSON `{"windows":[{"window_id":"w1","items":[{"line":12,"label":"question_start","confidence":0.9}]}]}`; do not solve, do not transcribe. Answer-key lines never sent (50.1), so no key ever reaches the model.
- Batch: <= 4 windows (<= 160 lines) per call. prompt_sha256 = sha256(template) as refine.py:370.
- Real: claude.run_claude(prompt, model="haiku", timeout_s, cwd=empty tmp) (same isolation as refine.make_real_llm). Mock: replies file via engine.mock_llm (refine.mock_llm :106 pattern). Dry-run: print windows (indices, kinds, line counts, no text beyond 60 chars each) + estimated cost, 0 calls.
- Token estimate per call: ~350 instructions + 160 lines x ~15 = ~2.8k own input, ~0.6k output; plus `claude -p` CLI overhead (unknown, assume <= 15k mostly cached; measured in V2).
- Cost per call (skill price table 2026-10-06): Haiku 5.5 $0.10/$0.50 per MTok -> ~$0.002-0.003; Haiku 4.5 $1/$5 -> ~$0.02. Alias `haiku` resolves in the CLI; the cap uses the reported total_cost_usd, so the estimate is not load-bearing.
- Per 22-page exam: normal 0 calls $0; weird <= 12 windows = 3 calls <= ~$0.01 (5.5) / ~$0.07 (4.5). Default cap `--max-cost-usd 0.10`.
### 50.4 Validation (owner: boundary.validate(obj, windows, min_conf=0.7, max_items=40) -> (hints, warnings))
- Per window: window_id known; items list <= 40; line int inside [start,end]; label in the 7; confidence number in [0,1]; no duplicate line. Any failure -> whole window ignored, warning `boundary_ai_invalid` {window, reason: json|schema|label|index|confidence|too_many|duplicate}. Bad JSON -> all windows of that call invalid. No retry (cost).
- confidence < min_conf -> dropped, counted `low_confidence`.
- Hints = {line: (label, conf)} only for lines that were suspects (a label on a non-suspect line is ignored).
### 50.5 Use of hints (owner: segment.segment(lines, hints=None)) - hint, never proof
- hints=None: identical to today (test). A hint is consulted only at suspect lines; a strong rule match (_Q with expected n, _OPT, _INTRO/_READ/_PART, known alias) always wins -> info `boundary_ai_overruled` (count).
- question_start on QS1: new question n = parsed number only if n == expected; else rejected (`boundary_ai_rejected`). Token promotion: >= 2 accepted exemplars with the same token -> other QS1 lines with that token use the same check without a call; warning `boundary_ai_marker` {token, count} so the user can add the word to _Q later (rule stays primary).
- question_start on QS2 (no number): split only when it closes a gap exactly: prev.n + 1 == next rule question n - 1 (or it is after the last question and the A-D run is complete); n = prev.n + 1; else no split (43.2 merge_suspect still declines).
- question_start on NB: keep; `other`/`option_continuation` on NB: glue into the stem only if numbering becomes consecutive.
- section_start / subject_start / passage / question_end after D: line not glued to D; goes to `pending` -> `context` of the next question (same path as _PART :43). subject_start never changes the exam Subject: warning `boundary_ai_subject` {line} for the user only. question_end = close after that line; option_continuation/other = today's glue.
- Every applied hint -> warning `boundary_ai_applied` {line, label, conf, origin: "ai"}; completeness (refcheck.incomplete_reasons) and numbering gates run unchanged after; no verification credit.
- Wiring: adapters call `reviewer(lines, page_of) -> hints` right before segment when config["boundary"] is set (same line list, so indices match); parts.select_pages(doc, spec, reviewer=None) passes it too (else `--pages` loses hints, D2).
### 50.6 Cost control + cache (owner: boundary.Reviewer, cli ingest flags, config/engine.json)
- `ingest FILE --boundary-ai {off,haiku}` (default from engine.json `"boundary_ai": "off"`), with exactly one of `--mock FILE|--dry-run|--real` (else exit 2, never defaults to real), `--max-cost-usd 0.10`, `--cache DIR`, `--boundary-trace FILE`.
- Stop before a call when spent + estimate > cap -> warning `boundary_ai_budget`; remaining windows keep the rule result; exit 0.
- Cache key = sha256("boundary\0" + window text) + prompt_sha256 + model; value = validated items. Per-run memory always; disk only with --cache; mock never reads disk.
- One cache only: new module src/exam_engine/ingest/replycache.py `ReplyCache(dir=None).get(key)/.put(key, obj)`, key namespaced (`boundary`/`page`). Whichever of TASK-047 (43.5) / TASK-050 lands first creates it; the other imports it. Cached hits cost 0 calls.
- Trace rows {window_id, window_sha256, cached, ok, cost_usd, reason}; no reply text written unless --boundary-trace.
### 50.7 Vision refine route: not applied
- Vision sees layout and printed numbers per page; refine has validate_refined + 40.2 bridge + 43.4 recovery. Its weak spot (page boundary) is 43.3/43.4. Adding a text window there would double-pay and disagree with the image. refine.py untouched (also avoids the dirty TASK-045 edits).
### 50.8 Skill exam-extraction (main writes): add under Rules
- "Text routes may ask Haiku about uncertain boundary lines only (`--boundary-ai`); the reply is a hint, AI-origin, gated by numbering and completeness; never proof, never the Subject, never answer-key lines."
- "An accepted new marker word (`boundary_ai_marker`) is a rule candidate: add it to segment._Q with a test, then the model is no longer asked."

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| bad JSON / schema / index | window ignored | `boundary_ai_invalid` reason |
| low confidence | hint dropped | count in boundary summary |
| hint vs strong rule | rule kept | `boundary_ai_overruled` |
| start breaks numbering | not split | `boundary_ai_rejected` |
| cap reached | stop calls, rules kept | `boundary_ai_budget` |
| CLI call fails | window ignored, run goes on | `boundary_ai_invalid` reason=call |
| too many suspects | top 12 by priority | `boundary_ai_skipped` |

## Unit tests (tier 0, synthetic text, mock replies; tests/unit/test_boundary.py)
1. hints=None and flag off: segment output and warnings unchanged on existing fixtures.
2. normal synthetic exam (Câu 1..10, A-D) -> 0 suspects, dry-run 0 windows.
3. QS1 `Bài 3:` / `Item 3)` / `Q3.` after Câu 2 -> suspect; mock question_start -> 3 questions consecutive, `boundary_ai_applied` origin ai.
4. QS1 token promotion: 6 `Bài N:` lines -> 2 exemplars sent (mock call count 1), all 6 split.
5. QS1 with wrong number (`Bài 7:` after 2) -> no suspect; forced hint -> rejected.
6. QS2 unmarked stem between two A-D runs, gap closes -> split with n=prev+1; gap not closing -> no split.
7. unknown heading `PHẦN 1: TƯ DUY` before a question -> SH; section_start -> not in option D, is context; subject_start -> warning only, Subject unchanged.
8. passage after option D -> QE; passage -> context of next question; option_continuation -> glued (today).
9. invalid JSON; unknown label; line out of window; confidence 1.5; > 40 items -> each `boundary_ai_invalid`, segment == rules.
10. confidence 0.4 -> ignored.
11. rule wins: hint `other` on `Câu 3` (expected) -> kept, `boundary_ai_overruled`.
12. budget: cap 0 with 2 batches -> 0 calls, `boundary_ai_budget`, exit 0.
13. cache: second run with --cache DIR -> 0 calls; prompt text change -> new key (miss).
14. answer-key lines (after `Đáp án`) never in any window; no prompt contains them.
15. CLI: --boundary-ai without mode -> exit 2; `--pages` keeps hints (select_pages path).

## Verification
| Item | command -> expected | tier |
|---|---|---|
| 50.1 | `python3 -I -m unittest discover -s tests/unit` -> OK, tests 1-15 | 0 |
| 50.1 V1 | `ingest <each examples/ + TASK-046 guide fixture + DGNL text> --boundary-ai haiku --dry-run` -> windows per exam (normal ~0), est cost | 0 |
| 50.3-50.5 V2 | user go, then `ingest <DGNL text> --boundary-ai haiku --real --max-cost-usd 0.05 --cache DIR` on <= 8 windows -> calls, cost, applied/rejected; compare each applied line with work/TASK-039/handoff/indep-*.md and the rules (TSV agree/disagree) | paid, < $0.05 |
| 50.6 | rerun V2 with same --cache -> 0 calls | 0 |

## Decisions (options)
- A (chosen) classify small windows of rule-uncertain lines: ~0 calls normally, strict schema, hint only.
- B model re-segments whole page text: ~22 calls/exam, re-transcribes text (drift), hard to validate.
- C vision-only: refine exists ($0.9/exam Sonnet), does nothing for DOCX/text route.
- D only hand-written regexes: free but misses unseen wording (the user's point); kept as the promotion path (50.5 marker).
- Limits: Haiku accuracy unknown, measured in V2 not claimed; the hint is a safety net behind the gates.

## Out of scope
- Vision refine route; MD format; auto-editing _Q from model output; per-question AI review.

## Defects
- D1 info segment.py:13 `_PART` matches roman PHẦN only; `PHẦN 1` arabic is glued into option D today (handled by SH, or a 1-line rule fix: user choice).
- D2 minor parts.py:75-80 select_pages re-segments from paragraph blocks without pdf `_strip_furniture` (pdf.py:362): `--pages` text path differs from full ingest; 50.5 must pass the reviewer there.
- D3 info tree dirty in refine.py/refcheck.py/api.py (TASK-045): 50 touches segment.py, pdf.py, docx.py, parts.py, cli.py, new boundary.py/replycache.py only.

## Coordinator decisions
1. Model: use the CLI alias `haiku` (resolved by claude -p), never a pinned version; the cap uses the reported total_cost_usd. Estimate per weird exam at most about $0.01 on Haiku 5.5 (about $0.07 if the alias resolves to 4.5): within the standing rule Haiku only for simple jobs with small context.
2. Cache: one shared reply-cache module with TASK-047 (43.5); whichever task lands first builds it, the other reuses it. TASK-047 is queued after this one, so TASK-050 builds `replycache.py` and TASK-047 reuses it.
3. D1 (`_PART` matches only Roman numerals, a `PHẦN 1` heading is glued into option D) and D2 (`select_pages` re-segments without the furniture filter and would drop hints on `--pages`) are in scope of TASK-050 because the hint map must survive page selection; D1 is a rule fix done first (rules before AI).
4. Default OFF everywhere (unit tests, CLI, config). A real Haiku run (V2) only with the user's go and the printed estimate; V1 dry-run is free.
5. Vision refine route not covered (the vision call already reads layout), as designed.
