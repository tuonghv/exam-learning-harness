# Phase 126 – Free text path fixes report (TASK-126, REQ-0133)

**Verdict: done.** Three issues from the approved paid DGNL 2025 English text-path solve (RAW-00344).

## Results
- Paid run (coordinator, before this task): DGNL 2025 English, 25 questions from native text, 24/25 correct
  against the key file, $0.25 (3 calls, claude-sonnet-5-5). The key was used for scoring only.
- A Multiple Choice question without options (error-finding items whose underlined A-D are lost in native text)
  now gets `[Incomplete: missing_text options_missing]`: the engine declines that question instead of refusing the
  file. The full exam files of DGNL 2025, DHQG 2024 and DGNL 2026 now parse (before: 5 errors each).
- A group instruction wrapped onto a lower-case next line stays one instruction (no stray `### Passage`).
- docs/guide/dgnl-real-exam.md: "Free text path" section (section slicing, pinned `--model`, limits).
- 5 tests (2 fail on old code, 3 guard unchanged behaviour); `--fast` KNOWN 4, NEW 0. Real inputs: only marker and
  instruction lines change (work/TASK-126/evidence/oracle.txt).

## Not changed
The diacritics check that failed 5 English answers was correct: the solver wrote Vietnamese without accents and the
retry did not fix it (solver-prompt matter, open). Underlined error-finding items still need refine.

## Spend
Roles waived (one-line changes; coordinator oracle + bite). This task: no paid run.
