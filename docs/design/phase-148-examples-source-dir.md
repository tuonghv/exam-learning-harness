# Phase 148 – check-examples: examples/dgnl source-document dir (TASK-148, REQ-0154)

Source: REQ-0154 (RAW-00370 "fix test_12b").

## Plan modes
No change to single-source or pipeline plans; only the `check-examples` validator.

## Design
- 148.1 `examples/dgnl/` holds the real DGNL 2026 PDF (REQ-0032; read by test_window_golden, test_assembly_qa), not
  few-shot pairs, so `check-examples` failed with `pairing: unknown subject dir` (3 known test failures since 2026-10-30).
- 148.2 `examples_check.SOURCE_DIRS = {"examples": ("dgnl",)}`, next to the LEGACY allowance: `_scan` skips that dir
  but reports any `.md` file in it as a stray file (few-shot cannot hide there). Only under `examples/`.
- 148.3 Remove the 3 tests from `config/test_tiers.json` known_failures.

## Verification
`exam.py check-examples` exit 0 on the repo; new unit test (pdf ok, .md stray, evals/ not covered) fails on old code;
`--fast` KNOWN 1 (docx lxml), NEW 0.
