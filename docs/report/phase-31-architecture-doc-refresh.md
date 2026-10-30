# Report phase 31: architecture doc refresh (TASK-031; REQ-0007)

Verdict: adopted. `docs/guide/architecture.md` (106 lines) now matches the real tree and `README.md` is 8 lines linking it and `examples/FORMAT.md`.

## What changed
- Components, Flow and Invariants rewritten from code (src/exam_engine, scripts/exam.py, tools shims, ingest, report views, language precedence); stale `tools/examples/tests` line removed.
- README cut from 48 to 8 lines; the tester found the dropped usage, so a "Run and test" section restores the unit/integration commands, parse/verify shapes, workspace/ and fake-claude notes (`work/TASK-031/handoff/test.md` D1, D2).

## Verification
- Independent tester check (`work/TASK-031/evidence/t031-docs.txt`): README <= 10 lines, links resolve, every named path/subcommand exists, six sections present, scan-toolkit grep 0, five claims match code.
- Observed by the coordinator: `python3 -I -m unittest discover -s tests/integration` OK (2 tests).

## Limitations
Docs only; the unit suite was not re-run. Product quality checked by recomputing paths against the tree, not by reading alone.

User instructions honoured: RAW-00132, RAW-00133 (quality over speed).
