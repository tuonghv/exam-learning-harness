# Phase 148 – check-examples: examples/dgnl source-document dir (TASK-148, REQ-0154)

**Verdict: done.** `check-examples` passes on the repo; 3 known test failures fixed (known list 4 -> 1).

## Results
- Cause: the real DGNL 2026 PDF (REQ-0032) is tracked in `examples/dgnl/` since 2026-10-30; the validator saw an
  unknown subject dir. The PDF is used by test_window_golden and test_assembly_qa, so it stays.
- `examples_check.SOURCE_DIRS = {"examples": ("dgnl",)}`: the dir is skipped, but any `.md` in it is a stray file.
- test_12b_real_repo_passes, test_check_examples_ok, test_cwd_independence_of_subcommands pass and left
  `config/test_tiers.json` known_failures. New test fails on old code. Evidence: `work/TASK-148/evidence/`.

## Issues
- Still known: test_d1_text_box (needs `lxml`, not installed).

## Spend
$0.
