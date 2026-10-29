# Phase 17: optional Claude refine stage (REQ-0021, TASK-017; EPIC-005)

## Goal
For pages flagged unreliable (math_possible, missing_text, bad numbering, OCR garble) a vision reply from `claude -p` (sonnet) rebuilds the questions as standard JSON, stored as suggestion (`origin: ai`), checked by code, never overwriting source. Off by default; cost only on `--real` after the user's go. Mirrors the solve mode gate.

## Command
`scripts/exam.py ingest-refine <file.pdf|doc.json> --pages SPEC (--dry-run | --mock FILE | --real) [--out refined.json] [--max-cost-usd 1.00] [--model sonnet] [--allow-key-pages]`. Never defaults to real. A file is re-ingested (`--ocr auto`); selected pages must be in the exam range: detected answer-key pages are refused (`answer_key_present`) unless `--allow-key-pages`. Pages sent = selected AND flagged (warnings with page: missing_text, bad_encoding, no_question_numbering, math_possible, status ocr). One call per page, max 2 attempts (one retry on invalid JSON/schema); dry-run prints page list, call count (<= pages x 2), cap, and exact prompt; no call.

## Code (`ingest/refine.py`)
- `pick_pages(doc, spec) -> [n]`; `render_page(path, n) -> png bytes` via fitz (zoom 2, <=5 MB else lower zoom), validated by the image adapter header check; image sent through `run_claude_images` (base64, tools off, empty cwd). Stream-json vs json output: first real call settles it; `run_claude_images` result handling stays in claude.py and a clear structured error (`stream_format`) is raised if the CLI rejects the flag combination, never silent.
- Prompt `prompts/dev/ingest/refine.md` (dev channel, not exam prompt; no answers, no keys): "transcribe only what is visible; do not solve; math in plain text per solver rules; unreadable -> `\"unreadable\": true`; do not invent". Output schema: `{"questions":[{"id","text","options":{"A":..},"figures":[..],"unreadable":false}]}`.
- Validate (`validate_refined`): schema, consecutive ids, options A-D for MCQ ids when original has them, no `answer`/`solution` fields (reject, a solver-like reply is a defect).
- Similarity: `difflib` ratio of folded refined text vs the page's OCR/native text per question; `needs_review` below `refine_min_similarity` (default 0.6) or unreadable; no accuracy claim.
- Store: `doc["refined"] = {model, prompt_sha256, pages:[..], questions:[{id,text,options,origin:"ai",page,similarity,needs_review}], calls, cost_usd}` plus `warnings`; `pages[].blocks` untouched (sha256 of pages equal before/after). `to_exam_text` ignores `refined` by default.
- Exit codes like solve: 0 ok, 1 needs_review present, 2 usage, 3 blocked/error.

## Tests ($0)
Mock reply files: valid -> stored, similarity computed, source blocks hash unchanged; invalid JSON then valid (retry); two invalid -> structured error; reply containing `answer` -> rejected; answer-guide pages without allow flag -> refused; unflagged page not sent (call count); dry-run makes no runner call and prints count/cap; no mode -> usage error; low similarity -> needs_review; real mode without runner mocked never called in tests. Mutation: skip key guard -> test fails.

## Real run (not in this task)
Benchmark on trial PDF pages 1-4: ~4 calls, cap $1.00, user's go required; also settles the stream-json question.

## Open questions
None (REQ-0021 Q1-Q3 accepted).
