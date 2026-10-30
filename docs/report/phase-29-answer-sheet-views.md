# Report phase 29: answer sheet + learning view (TASK-029; REQ-0034, REQ-0035)

Verdict: adopted. Reports now start with a compact per-subject answer sheet and `exam.py report --view learn` gives a student-friendly learning view; solver, schemas, engine.py and `build_markdown` are unchanged.

## What was built
- `build_answer_sheet` (header `<Subject> – <N> Questions`, 5 per row, 2-digit ids as stored, circled Ⓐ-Ⓓ, — for null/Open/non A-D), written after the title of report.md/html/pdf and to `answers.md`.
- `build_learning_view`: answer, Why, Steps, Key concept / Common mistake only if present (phase 1 reuses `explanation` + `solution`, no extra LLM cost).
- `--view sheet|learn` on `exam.py report` (default sheet, bad value rc 2).
- Font: "Noto Sans Mono CJK SC" added to the `code` stack in md2html.py (DejaVu Sans Mono lacks U+24B6-24B9); cells padded by display width.
- Files: reporter.py, cli.py, md2html.py, tests/unit/test_exam_report.py only (evidence `work/TASK-029/evidence/ac3-diffstat.txt`).

## Tests and verification
- Unit: 12 new tests pass; full suite 523 run, 3 failures (examples/dgnl pairing) identical on a clean tree (511 run, same 3), so unrelated. Two mutations (drop zfill, null -> 'None') were caught (work/TASK-029/handoff/test.md).
- Real data (tier 0): — count equals `"answer": null` count in each result.json (Vietnamese 9, Science 9, English 2, Math 2), ids 01..30 (`work/TASK-029/evidence/`). `--view zzz` rc 2 (`evidence/view-bad-rc.txt`). PDF page render observed by the coordinator at `work/TASK-029/v/sci/pg-01.png`: columns aligned.
- Verifier: PASS on all ACs (work/TASK-029/handoff/verify.md).

## Limitations
- answers.md may drift one column in terminals that draw circled letters 1 wide.
- A combined multi-subject sheet and PDF-original numbering (31..60) are out of scope; ids print as stored.
- key_concept / common_mistake generation is phase 2, not built.

## For the user
Nothing to configure. TASK-030 (REQ-0036) adds the language default (vi) and `--lang`.

User instructions honoured: RAW-00121, RAW-00123, RAW-00124, RAW-00125 (RAW-00124/00125 are carried by TASK-030).
