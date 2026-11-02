# Report phase 59: page-image check for flagged questions (TASK-059; REQ-0059)

Verdict: adopted, with the real paid check still pending (REQ-0063). Before round 1 the engine now prints `WARN` for each question whose stem points at a figure, table or passage that is not in its text. With `--pdf FILE` (cfg `image_pdf`, `--max-image-pages N`) the engine makes ONE extra capped image call after the text rounds for the flagged questions only: source pages come from `q.pages`, questions are matched by printed id + stem prefix (never by counting), answer-key pages are refused, the call counts in `call_cap` (+1) and `max_cost`, and it is captured in the plan run (`calls/`, page list, `page_sha256`; images are not stored). Text and image answers are reconciled with `cross.same_answer`: agree/differ -> `needs_review`; `source: "image"` appears in result.json, reports and the metrics counters `image_checked` / `image_changed`.

## Safety rules (decision G1)
Unreadable or absent image, render/call failure, non-PNG or oversize render (8 MB), malformed reply: the text results stay unchanged and a finding is added; a text answer already given is never overwritten without a recorded reason and a question already declined stays declined. Without `--pdf` all output is byte-identical to before (25 inputs checked against baseline 760fbac) and only the stderr warning is new. The warning may also flag questions the text already answered (Q7, Q19, Q20 on the trial exam): it warns, never declines.

## Evidence (docs/report/evidence/TASK-059/)
suite-final.txt and head-failures.txt vs baseline-failures.txt (same 4 known failures as baseline 083d0e4), qa-no-pdf-identity.txt, qa-full-suite.txt, test.md (9 mutations killed), verify.md. Found and fixed on the way: mock render stub failed the new PNG guard so `--pdf --mock` made no image call (verifier D1), the result schema rejected finding source `image` (found by the new CLI test), ids matched by position were only caught by the new test.

## Limits
No paid run: the real-slice check on the TASK-020 trial pages (Q1, Q7, Q10, Q18 with source-page lines added; about 0.20-0.30 USD, cap 0.50) is REQ-0063 and waits for the user's go (question Q-1793619815). The real page renderer (`refine.render_page`) is exercised only through a fake render in tests. The verifier had no shell and judged from code and saved evidence.

User instructions honoured: RAW-00169.
Evidence files for crosscheck: docs/report/evidence/TASK-059/test.md, docs/report/evidence/TASK-059/verify.md (index: docs/report/INDEX.md).
