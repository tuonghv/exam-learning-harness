# Report phase 47: whole-question window, bounded recovery and page cache (TASK-047; REQ-0051)

Verdict: adopted for the free (mock) path; the real-page proof is pending (REQ-0064). The PDF adapter now emits `page_cut_suspect` warnings from native text signals (they never remove a page). In refine, a deterministic cut test (last question without 4 options, ends mid-sentence, next page starts without a number) drops the open question from page N, and the call for page N+1 also receives page N's image (a window of up to 3 pages) and returns the question whole. Recovery is bounded (at most 2 extra pages per chain, 4 per run) and the cost cap is checked before every call, windows and fallbacks included. Each page call is cached by sha256(page image) + prompt hash + model (memory always; disk with `--cache DIR`; mock runs never read disk; a wrong-shape cache entry is a miss) and the trace rows carry `page`, `pages`, `png_sha256`, `cached`. New flags: `--no-recover`, `--no-window`, `--cache DIR`; the dry-run prints pages, windows planned, calls and estimated cost. Prompt rule 11 is in the dev channel only (no release copy of the refine prompt exists).

## Evidence (docs/report/evidence/TASK-047/)
suite-final.txt and head-failures.txt vs baseline-failures.txt (same known failures as baseline 083d0e4), test.md (design tests 1-15 mapped, mutations killed after 10 added tests), verify.md. Gold oracle (mock replies from synthetic gold PDFs): 25 questions, 0 orphans, cross-page counts equal the gold, windows used. With no cut and no `--real` outputs are byte-identical to baseline 2cc9808 except 6+ informational `page_cut_suspect` warnings on DGNL.

## Limits
No paid run: pages 7-8 and 14-15, then 5-16 on the real DGNL PDF are REQ-0064 and wait for the user's go (question Q-1793622303, under about $0.30 with a dry-run first). `EST_CALL_USD` is 0.08 per call, conservative: measured single-page mean 0.036 (max 0.045); window calls with up to 3 images are unmeasured (estimated 0.08-0.11), so the 22-page `--all-pages` dry-run shows about $1.76. The verifier had no shell and judged from code and saved evidence.

User instructions honoured: RAW-00146 (completeness guide), RAW-00152 (small slices first, cost discipline).
Evidence files for crosscheck: docs/report/evidence/TASK-047/test.md, docs/report/evidence/TASK-047/verify.md (index: docs/report/INDEX.md).
