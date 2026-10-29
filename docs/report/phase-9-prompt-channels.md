# Report: TASK-009 prompt channels (REQ-0013)

**Verdict: adopted.** Prompts live in `prompts/dev/` (editable) and frozen `prompts/releases/v1.0.0/` (sha256 manifest). The engine defaults to the release; `--channel dev` and `--prompt-version` select others; `result.json` records `run.prompt`.

## Commands
`exam.py prompts release vX.Y.Z` (never overwrites), `exam.py prompts verify [V]` (exit 1 on mismatch).

## Verification
- Suite 222 unit + 2 integration OK; `prompts verify` OK; mutation: a dev-only marker is absent from the default prompt and present with `--channel dev`, release still verifies.
- Verifier: AC1-AC4 pass; found major D1 (`--prompt-version ../dev` escaped releases/). Fixed: version regex in settings, CLI exit 2, tests added. D3 (utcnow) and D4 (version with dev) fixed; D2 covered by new tests.

## Limitations
- A release is as trusted as git history; verify detects edits only against its own manifest (a commit can change both).
- Language variants and the interface validator are REQ-0014.

## Next
REQ-0014.
