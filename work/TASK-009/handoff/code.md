PROGRESS: COMPLETE
SKILLS: python

Files: src/exam_engine/settings.py (PROMPT_SOURCE, use_prompts, prompt_source, prompt_root, read_prompt), src/exam_engine/pipeline/prompts.py (new), cli.py (--channel/--prompt-version, `prompts` subcommand), engine.py (run.prompt), config/engine.json, schemas/result.schema.json (optional run.prompt), scripts/exam.py docstring, README.md (2 lines), prompts/dev/* (moved), prompts/releases/v1.0.0/* + MANIFEST.json (created via `prompts release v1.0.0`), tests/unit/test_prompt_channels.py (new), test_req0012_acs.py, test_settings.py (path/config fixes).
Note: the git mv command is refused for the coder role; I used plain mv, so main must stage prompts/ (renames are then detected).
Tests: unit 219 OK, integration 2 OK.

## Defects
None. Note: the test_6_4 regex test now exempts the literal "prompts" subcommand name in cli.py.
