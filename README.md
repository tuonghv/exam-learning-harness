# exam-learning-harness

Checkable input/expected-output exam examples (few-shot and eval) plus a stdlib Python engine to solve, verify, report and score them.
- Layout: `src/exam_engine` (engine; `adapters/claude.py` is the only model call), `scripts/exam.py` (CLI), `prompts/`, `schemas/`, `config/` (`subjects.json`), `tools/examples` (thin shims), `tests/`, `examples/`, `evals/`.
- Run (always `python3 -I`): `scripts/exam.py solve`, `exam.py parse`, `exam.py verify`, `exam.py report [--view sheet|learn]`; real runs need `--real` (paid).
- Architecture, flow, invariants, test commands: `docs/guide/architecture.md`
- Example format standard: `examples/FORMAT.md`
- Requirements: `docs/req/`; design: `docs/design/`; guides: `docs/guide/`
- Git hook (once per clone): `git config core.hooksPath .githooks` enables the advisory post-commit check (`tools/post_commit_check.py`: left-behind changes, files > 1 MiB, code without `Task:` trailer, review-ledger problems; warns, never blocks; off with `POST_COMMIT_CHECK=0`) and auto-pushes each commit of a non-main branch to `origin` in the background (`AUTO_PUSH=0` off; log `.git/autopush.log`; `main` is never pushed by the hook).
- Delete guard (REQ-0156): a PreToolUse hook (`.claude/hooks/delete_guard.py`) denies unrecoverable deletes for every session and role (repo root and parents, `./*`, empty `$VAR`, plans/ reports/ input/ results/ .git, `git clean -x`); clean agent scratch with `bash .claude/scripts/clean-work.sh TASK-NNN`. The post-commit hook also runs `exam backup` in the background when plans/ or input/ changed after the newest backup (`AUTO_BACKUP=0` off).
