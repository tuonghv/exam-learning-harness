# Phase 9: prompt channels (REQ-0013, TASK-009; EPIC-004)

## Goal
Development edits prompts freely; runs use a frozen release unless asked. Answers accepted 2026-10-29 (RAW-00046): releases in git, semver; `prompts/` is the only engine source.

## Layout
- `prompts/dev/` = today's `prompts/{system.md,exam/,subjects/,verification/}` moved with `git mv`. Editable.
- `prompts/releases/vX.Y.Z/` = frozen copy of dev + `MANIFEST.json` `{version, created, files:{<rel>: sha256}}`. First: `v1.0.0`.
- `config/engine.json` gets `prompt_channel` ("release") and `prompt_release` ("v1.0.0").

## Code (reuse `settings.read_prompt`; all callers stay unchanged)
- `settings.py`: `PROMPT_SOURCE` state + `use_prompts(channel=None, version=None)` and `prompt_root()`; `read_prompt(rel)` reads under `prompt_root()`. Default from config. `PROMPTS_DIR` stays the base `prompts/`.
- `pipeline/prompts.py` (new, stdlib): `release(version)` (copy dev -> releases/version, refuse if exists, write manifest), `verify_release(version=None)` (sha256 of each file vs manifest; extra or missing file = error), `prompt_info()` -> `{channel, version}`.
- CLI: `--channel {release,dev}` and `--prompt-version V` on `solve`; `scripts/exam.py prompts release V` and `prompts verify [V]` (exit 1 on mismatch).
- `result.json` `run.prompt = {channel, version}` (schema: add optional property; keep additionalProperties rules).
- A release path is never written by the engine; `release()` is the only writer and refuses to overwrite.

## Tests (AC4 and others)
default solve reads release not dev (edit a dev file with a marker, mock run: marker absent from the captured prompt); `--channel dev` reads it; release refuses an existing version; verify fails after a one-byte edit of a released file; result.json carries channel/version; existing 211 tests stay green (fix path literals to dev only where a test reads a prompt file).

## Out of scope
Language variants and contracts (REQ-0014); changing prompt text.
