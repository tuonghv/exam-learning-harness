# Report: TASK-003 example layout, checker, scorer (REQ-0002)

**Verdict: adopted.** AC1-AC5 verified by real runs; one documented limitation.

## Task and requirement
REQ-0002: validate every example in the `examples/FORMAT.md` standard, keep few-shot and eval apart, never expose eval keys to the solver. Design: `docs/design/phase-3-example-checker.md` (Q1-Q5 accepted, RAW-00030).

## Implementation (commits)
- `92e57d4`: `tools/examples/exam_parse.py` (shared parser), `check_examples.py` (pairing, sections, headers, options A-D, Verification, Literature quotes, disjoint ids/text, input-key, key-leak, legacy allowance for `examples/english/expected-001.md` pinned by path + sha256), `score_eval.py`, `examples/README.md` (55 lines).
- `af46bd9`: 28 unit tests under `tools/examples/tests/`.
- `examples/FORMAT.md`: `Skill` and `Language` made optional (Q5).

## Reuse
The parser is shared so the EPIC-003 engine (REQ-0008/0009) imports it; module names follow `docs/design/phase-2-exam-pipeline.md`. Stdlib only, Python 3.8, run as `python3 -I`.

## Tests and verification
- 28 unit tests OK; each of 13 mutations of the tools (tester 10, coordinator 3) made its matching test fail.
- Real runs on fresh temp copies (`work/TASK-003/handoff/evidence.md`): removed pair, duplicate id, duplicate text, Solution or `Final answer:` in an eval input, key without `Status: Verified`, three options, edited legacy file all exit 1 naming the file; the valid pair and the real repo exit 0. The scorer reads keys only from `--keys-dir`, prints no key text, exits 2 on overlapping dirs.
- Verifier (`work/TASK-003/handoff/verify.md`): AC1-AC5 PASS. Its reply was transcribed by the coordinator because the role had no Bash and no file brief.

## Limitations
- A short answer written mid-line in an eval or few-shot input is not caught (only line-start markers and copied Solution/Explanation lines of 40+ chars). Stated in `examples/README.md`; a human reads each new eval input. Optional later guard: flag eval inputs that contain the key's Final answer value.
- "One fresh call per eval input" is documented, not enforced by these scripts; the EPIC-003 engine enforces it.
- Cross-file checks have only run on the one English pair and synthetic cases; REQ-0003/0004 add real data.

## Next
EPIC-003 engine build (REQ-0008 design is done), then REQ-0009 real-run benchmark (needs the user's go), REQ-0003/0004 examples.
