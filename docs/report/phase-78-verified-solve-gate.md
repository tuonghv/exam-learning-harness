# Report phase 78: verified solve gate (TASK-078; REQ-0024)

Verdict: done and verified; dormant on real runs today, because no document in the pipeline carries per-question verification data yet.

## What it does
- `ingest --exam-out` keeps only questions that meet `min_verification` (`config/engine.json`, default `verified`; `--min-verification any` restores unverified and needs_review ones; `rejected` is never solved).
- Skipped questions go to the `.assembly.json` sidecar, then to `result.json` (`skipped_unverified`, `summary.skipped_unverified`) and a Skipped section in the report. They are never FAIL and never counted in metrics or the exit code.
- A question without a verification key inside a document where others have one counts as unverified. All questions skipped -> clear error, exit 2.
- Solver, verifier, decision logic and prompts are untouched (AC4).

## Measured
- Re-ingest of all 4 DGNL 2025 subjects (120 questions), code before vs after: exam.md byte-identical in all four; assembly differs only in the exam file name.
- 26 gate tests pass (1 expected failure documents a pre-existing refined-offset oddity, QA-1). The full suite keeps its 4 known failures, which reproduce on the old code (docx textbox, check_examples, req0012 cwd, scripts_exam).
- One guard test (`test_48_releases_untouched`) compared all of `config/engine.json`; it now compares only the release selection.

## Also measured in this stretch (2025 DGNL, answers used for scoring only)
- Noise baseline: the same inputs solved twice flipped 7 of 120 answers (5.8%); both runs score 111 of 120 (declined counted wrong). A change under about 6 questions cannot be told from noise on one exam.
- Key check: a blind re-solve of the 12 questions wrong in either run agrees with the key on 4 (56, 106, 108, 117) and with our answer, not the key, on 8 (16, 17, 27, 39, 60, 67, 107, 111). Strongest key-error candidates, high confidence: 16, 67, 111. The blind solver is the same model family, so only the official solutions can settle them. Not counted as correct.

## Limits
- Dormant until REQ-0022/0025 style verification statuses are written into documents.
- The inspect report shows ungated rows (low).
