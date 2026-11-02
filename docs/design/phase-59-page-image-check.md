# Phase 59 - Page-image check for flagged questions
# Phase 59 - Page-image check for flagged questions (draft for docs/design/phase-59-page-image-check.md)
Task: TASK-059 · REQ-0059 (RAW-00169) · Status: draft · Supersedes/narrows: phase-55 55.7; base: work/REQ-0058/handoff/addendum.md F1, N1, N3
## Goal
A question whose text refers to a figure/table/passage that is not in the text (refcheck) is warned about before round 1 and,
with `--pdf FILE`, re-asked once with only its source page images; text and image answers are reconciled and the
answer's `source` is recorded. Seen when: trial Q10/Q18 (declined on text, right on images, TASK-020 RESULT.md:5-6) get an
image answer that the key scores, unflagged questions unchanged, cost in result.run.
## Constraints
- No `--pdf` -> prompts, result.json, config.json, calls/ byte-identical to today (only new stderr WARN lines).
- Trust: no tools adapter (claude.run_claude_images, claude.py:53, base64 stdin, <= 5 MB/img); only listed pages; key pages refused (no `--allow-key-pages` on solve).
- Caps: image call goes through Runner.call (cost cap + call cap checked before it, engine.py:37-41).
- Cache: solve has no reply cache (prompt_sha256 is recorded only, planrun.py:127); ingest cache untouched. Nothing stale to key.
## Known incidents
- N3: route B by reading order -> all count_mismatch (RESULT.md:3). Here ids come from our list, never from counting.
## Plan modes
- `--dry-run`: prints WARN lines, image targets, pages, cost estimate, the image prompt; no render, no call.
- `--mock FILE`: image call takes the next mock reply (as cross-solve, cli.py:690-693); page bytes stubbed, no fitz.
- `--real`: renders pages via refine.render_page (refine.py:73), one extra call.
## Design
### 59.1 Pre-solve WARN (owner: engine.run, engine.py:150)
- New pure `engine.visual_flags(exam) -> {id: [parts]}` = the zip at engine.py:87-88 (build_result reuses it; same input text).
- After `skip = incomplete_ids(exam)`, before round 1, for each flagged id not in skip, stderr:
  `WARN: question <id> refers to <parts> not in text (pages <a-b>|pages unknown); image check: on|off (no --pdf)|off (no pages)`.
- Warn only, never decline (regex precision unmeasured: trial Q7, Q19, Q20 also match `_FIG` and text answered them).
### 59.2 Trigger set and page cap (owner: new pure `engine.image_targets(exam, flags, skip, max_pages, key_pages, have_pages)`)
- Returns `(targets: [id], pages: [int], skipped: {id: reason})`. Candidates = flagged ids not in skip, ascending.
- Per candidate: no `q["pages"]` -> skipped `no_pages`; page in key_pages -> `answer_key_page`; page not in doc -> `page_absent`;
  else add if `len(union | q.pages) <= max_pages`, else `page_cap`. `max_pages == 0` -> all `disabled`.
- Every skipped id gets finding `image_skipped: <reason>` (decision.finding source "image") and keeps its text result.
### 59.3 Image call (owner: new `cross.flagged_prompt(exam, items) -> str`; `Runner.call(prompt, tag, images=None)`)
- items = `[(id, printed, stem_prefix)]`; printed = id + offset (parser._OFFSET_RE) or None; stem_prefix = first 80 chars of the
  first line of `q["stem"] or q["text"]`.
- Prompt = `solver.base_prompt(exam)` + `Language:` + FLAGGED_RULES: "Only these questions are asked, in the attached pages:
  `id <id> (printed <p>): "<prefix>..."` per line. Identify each by its first words (printed numbers may restart per part);
  answer with exactly these ids. Read figures/tables from the images. If the question or its figure is not readable or not
  on the pages, set answer_status non-answered with the reason; never guess." Reply = SOLVE_OUT, parsed by cross.parse_reply.
- Runner gets `llm_images` (ctor arg, default None). `call(..., images=pngs)` -> `self.llm_images(prompt, pngs)`; same
  cost/call accounting, log line gains ` images=<n>`, sink called as `sink(n, tag, prompt, c, pages=pages)`.
- `call_cap(cfg) = 1 + 2*max_attempts + (1 if cfg.get("image_pdf") else 0)`.
- Placement: after the text loop (engine.py:165), before scorer.apply_key; skipped if `stopped`. One call, no retry
  (malformed reply -> finding `image_malformed`, text results kept).
- Render: CLI passes `render(n) -> bytes`; RefineError/OSError -> no call for that id set; finding `image_unavailable: <msg>`.
### 59.4 Reconciliation (owner: new `engine.apply_image(recs, got, targets)`)
| text rec | image reply for id | result |
|---|---|---|
| answered | answered, `cross.same_answer` | text rec unchanged, `source: "text+image"` |
| answered | answered, differs | UNCERTAIN `needs_review: text/image differ`, answer = text, finding `image_differs` (image answer in message), `source: "text+image"` |
| declined / open | answered | rec.ans = image answer, code checks + `decide_rec` (review None -> UNCERTAIN `no_review`), finding `image_answer`, `source: "image"`, attempts += 1 |
| any | declined / missing id | text rec unchanged; if text declined, reason `solver_declined: missing_text (<parts>; image: <reason>)` (AC2) |
- Reply ids not in targets: ignored (finding on none; logged count in WARN). Missing id -> reason `image: not in reply`.
- key scoring (scorer.apply_key) then runs on the final answer.
### 59.5 Result, plan run, reports, metrics
- result.json question: optional `source` enum `text|image|text+image`, only for targets (schemas/result.schema.json items.properties).
- plan run: image call is a normal capture `calls/NNN-{prompt,reply}.txt`; index line gets `"tag": "image", "pages": [..]`
  (key only on image lines; planrun.record new kwarg `pages=None`). No PNGs stored (sha256 per page in index: `page_sha256`).
- config.json: `image_pdf`, `max_image_pages` added to cfg only when `--pdf` given (config_sha256 unchanged otherwise).
- reporter.py:181 block: `- Source: <source>` line when present; review pack unchanged.
- metrics.compute counts (56.1 catalogue, add rows, nothing renamed): `image_checked` = #source present, `image_answered`
  = #source=="image", `image_differs` = #reason startswith `needs_review: text/image`; all None when no question has `source`.
### 59.6 CLI (owner: cli.solve_main)
- `--pdf FILE` (PDF or ingest doc.json, loaded like cross_main cli.py:652-661 -> extract `_load_source_doc(path)` shared by both);
  `--max-image-pages N` (default 4, >= 0). cfg key `image_pdf` (NOT `pdf`: cfg["pdf"] = report PDF flag, cli.py:83).
- key_pages = pages of `answer_key` parts (doc["parts"] or parts.find_parts, same source as refine.check_key_pages).
- render = `refine.render_page(_refine_source(a, doc), n)` in real mode, stub `b"\x89PNG"` in mock.
- No `--pdf`: 59.1 WARN only, all else as today. `--max-image-pages` without `--pdf`: usage error exit 2.
- Header: `calls <= N, cap $X; image check: <k> questions, pages <list>, est. $<0.03 + 0.035*pages>`.
## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| no --pdf | text only | WARN per flagged id |
| q has no Source pages | id skipped | WARN `off (no pages)`, finding image_skipped: no_pages |
| page in answer key | id skipped, no render, no call | WARN + finding image_skipped: answer_key_page |
| page unreadable / render error / > 5 MB | no call | finding image_unavailable; declined stays declined with reason |
| wrong page (question not on it) | model declines per rules | reason `image: <model reason>` |
| reply has other ids / count differs | only target ids used | finding image_missing for absent ids |
| cost or call cap hit | Stop as today, image not run | result.run.stopped |
| malformed reply | text kept | finding image_malformed |
## Unit tests (tier 0, mock LLM, tests/unit/test_image_check.py)
1. visual_flags: Q10-like stem ("bảng biến thiên như hình dưới đây", no table) flagged; plain MCQ not; WARN text on stderr.
2. image_targets: pages union, cap 4 -> page_cap skip, key page -> answer_key_page, no pages -> no_pages, max 0 -> disabled.
3. no --pdf golden: prompts sent, result.json, config.json equal to a run before the change (fixture exam with a flagged q).
4. key page in union -> llm_images never called (counter = 0).
5. flagged_prompt lists `id`, prefix, no reading-order wording; reply with extra id 99 -> ignored; missing id -> text rec kept.
6. apply_image table rows 1-4 (same, differ -> needs_review, declined->image answer source image, image declined -> AC2 reason).
7. Runner: image call counted in calls/cost; cost cap before it raises Stop; call_cap +1 only with image_pdf.
8. planrun index line tag image + pages; metrics image_* counts and None without source; schema accepts `source`.
9. CLI: `--max-image-pages` w/o --pdf -> 2; dry-run prints image prompt, no render.
## Verification
| Item | command -> expected | tier |
|---|---|---|
| 59.1-59.6 | `python3 -I -m unittest discover -s tests/unit` -> OK, new tests pass | 0 |
| dry-run | `scripts/exam.py solve <slice.md> --pdf work/ingest-trial/doc.json --dry-run` -> WARN for flagged, image prompt, est. | 0 |
| key refuse | same with a slice whose Source pages include 5 -> `answer_key_page`, no call | 0 |
| AC3 real (PAID, user go) | see below | 2 |
### Paid item (needs the user's go, listed apart)
- Slice of work/TASK-020/real/exam.md: Q1 (control, unflagged), Q7 (flagged, text answered), Q10, Q18 (flagged, text declined),
  with `Source pages:` lines added (Q18 = page 3, doc.json:585; Q1/Q7/Q10 pages: main greps doc.json, free).
- `solve <slice> --pdf <math_12_graduation_2026_001.pdf> --key <trial key> --real --max-cost-usd 0.50`
  -> Q10, Q18 `source: image` and key-correct; Q1 no `source`; Q7 `text+image`; cost in result.run.
- Estimate: text round+QA on 4 q ~$0.08-0.15 + image call 2-3 pages ~$0.10-0.14 (route B: 4 pages $0.168, cross.trace.json:12)
  = ~$0.20-0.30. "One image call" holds; the text round is unavoidable in `solve`.
## Decisions (proposed; main/user confirm)
1. Reuse route B machinery (llm_images, render_page, parse_reply, same_answer) with a new id-list prompt, not cross_solve
   itself: cross_solve sends all pages and compares by count (N3). Rejected: calling cross-solve per flagged id (2 calls each,
   reading-order ids); image-first for flagged ids (no text answer to reconcile, breaks "others unchanged" golden).
2. Image call after text rounds (needs the text answer for 59.4); one call, no retry (smallest; cost bound +1).
3. Image-only answer stays UNCERTAIN `no_review` (text QA cannot see the figure); key scoring shows correctness.
4. Flag name `--pdf FILE` per brief beside `--no-pdf` (report). Alternative `--source-pdf` is clearer; recommend `--pdf` +
   help text "source PDF for page-image check" for parity with cross-solve.
## Gaps
- G1 (decision, AC2 wording): when the text answered and the image is unreadable, I keep the text answer (finding only);
  AC2 "decline" applied only when no answer exists. Recommend this; main confirms.
- G2: work/TASK-020/real/exam.md has no `Source pages` lines (pre-55.6) -> real check needs the slice prep above.
- G3: FLAGGED_RULES live in code (like IMAGE_RULES), not in the versioned prompt release; result.run.prompt does not cover
  them. Acceptable for now; move to prompts/ if the text changes often.
- G4: marker-declined ids (incomplete_ids) are not image-checked (AC1 scope); possible follow-up.
## Defects
- none in code. Risk: cfg key `pdf` already means report PDF (cli.py:83, engine.py:189) -> must use `image_pdf`.
## Out of scope
Per-question crops, image-first solving, second model family, N5 stability.
Nova

## Decisions (coordinator)
- G1 accepted: when the page image is unreadable or absent, a text answer already given is kept (marked needs_review, never overwritten); a question already declined stays declined with its reason. This refines REQ-0059 AC2.
- Flag name: `--pdf FILE` (cfg key `image_pdf`). Without it everything is byte-identical and the pre-solve WARN only.
- The real-slice run (about $0.20-0.30, cap $0.50) is the only paid item and needs the user's go: it is NOT part of the autonomous run; tests use a mock LLM.
