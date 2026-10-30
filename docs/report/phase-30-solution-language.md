# Report phase 30: solution language (TASK-030; REQ-0036)

Verdict: adopted at tier 0. Every subject (English included, unknown subject included) now defaults to Vietnamese explanations; `--lang vi|en|auto` overrides; learn-view labels follow the solution language. No re-solve was run.

## What changed for the user
- Default `vi` for all subjects: config/subjects.json english `en` -> `vi`.
- Precedence: `solve --lang` > exam header `Language:` > subject policy > `vi`. `auto` is resolved in code (`detect_lang`, dominant language) to vi|en; `--lang fr` exits 2.
- Learn view labels localized (vi: Đáp án, Vì sao, Các bước, Khái niệm chính, Lỗi thường gặp; en unchanged). The answer sheet and `build_markdown` are unchanged.
- Docs: examples/FORMAT.md:28 default is now vi; docs/prompts/exam/solver.md notes that `auto` is resolved in code.
- Files: config/subjects.json, cli.py, engine.py, router.py, reporter.py, utils/text.py, tests (evidence `work/TASK-030/evidence/ac-diffstat.txt`: no schema/solver/prompt change).

## Tests and verification
- Unit: 531 run, only the 3 known pre-existing failures (examples/dgnl pairing). Four mutations caught (work/TASK-030/handoff/test.md).
- Tier-0 real checks: precedence rows 1-4 by `solve --dry-run`, learn view of work/dgnl-real/run-English/result.json in vi/en/auto, sheet byte-identical (`work/TASK-030/evidence/tier0-*.txt`). Verifier PASS (work/TASK-030/handoff/verify.md).

## Limitations / needs your go
- English exams now use the `lang/vi` prompt variants (dev channel, v1.1.0+) in a paid run; not yet observed. A paid `--real --lang en`/default re-solve of one subject is pending the user's go.
- Generated English exams carry `Language: en` in their header (genexam.py:40) so they stay English; change genexam if all should be vi.
- The report body outside the learn view stays English by design.

User instructions honoured: RAW-00124, RAW-00125, RAW-00126.
