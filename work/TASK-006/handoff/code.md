PROGRESS: COMPLETE
SKILLS: coding, python

# TASK-006 coder handoff (file was not written by the coder; recorded by the coordinator from its report and my own checks)
- Built S1-S6: src/exam_engine (settings, cli, engine, adapters/claude, core/{schema,safe_eval,decision}, pipeline/{parser,router,solver,verifier,scorer,reporter,examples_check}, utils/md2html), scripts/exam.py, schemas/, config/, prompts/, tests/unit, tests/integration, README.md, pyproject.toml, .gitignore.
- tools/examples/*.py are now <=10 line shims; old tests moved to tests/unit.
- Deviations (coder): `--out` default not added; config `checks`/`score_basis` applied; env `EXAM_ENGINE_CONFIG_DIR` added.
- Coordinator checks: unit 186 OK, integration 2 OK; old exam_run.py and scripts/exam.py solve print the same summary line (pass=1 ... calls=2) and rc 0; only src/exam_engine/adapters/claude.py:45 builds a `claude` argv.
- Stale references to tools/examples/tests exist in CLAUDE.md, skills, docs/guide/toolkit-reference.md (out of scope, need the user).
