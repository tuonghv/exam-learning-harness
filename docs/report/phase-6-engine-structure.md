# Report: TASK-006 engine restructure (REQ-0012)

**Verdict: adopted.** One package `src/exam_engine`; behaviour unchanged.

## Built (commits `b4336ce`, `41c1f49`)
- `src/exam_engine/{settings,cli,engine}`, `adapters/claude.py` (only `claude` caller), `core/`, `pipeline/`, `utils/`; `scripts/exam.py` (solve|parse|verify|report|check-examples|score).
- Top-level `prompts/`, `schemas/`, `config/` (JSON), `tests/{unit,integration}`; `tools/examples/*.py` are thin shims; README documents it.

## Verification
- 198 unit + 2 integration OK; 3/3 mutations killed; old and new CLIs give the same summary and exit codes; cwd-independent.
- Key read only in `pipeline/scorer.py` after DECISION; no key text in prompts; a new subject needs only config + prompt file.
- Verifier: AC1-AC6 pass; defects low.

## Open (needs the user)
- `CLAUDE.md`, skills and `docs/guide/toolkit-reference.md` still name `tools/examples/tests`; not edited.
- A few path literals outside `settings.py`; `claude-sites.txt` evidence is weak (grep only).
- Shims stay until you say remove.
