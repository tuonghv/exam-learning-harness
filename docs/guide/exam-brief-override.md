# Exam brief override

The coordinator pastes this block as the first lines of every EPIC-002 role brief
(designer, coder, tester, verifier, inspector).

```
OVERRIDE (exam/learning harness, EPIC-002):
1. Domain: exam content (Maths, Physics, English, Literature). `examples/FORMAT.md` is the input/expected standard.
2. Ignore leftover scan, frozen-prompt or security-severity text in role bodies and skills.
3. Do not run `.claude/scripts/*`, `tests/*`, `req.py`, a scratch kit, `claude -p` or network tools.
4. Run only `tools/examples/*` with `python3 -I`; everything outside the brief's write list is read-only.
5. Write only the files the brief names, plus your handoff.
6. Content defects (wrong key, unit, quote) go in the handoff under `## Defects`.
7. Never put exam prompts under `docs/prompts/` (commit-check.sh freezes that path).
8. Verify with skill `crosscheck`, section "Exam content oracle" (Tier 1).
```

Why: the roles and skills were inherited from a different project; the block overrides what no longer
fits without rewriting the role bodies. Eval keys must never reach the solver, so the oracle also
checks that keys do not leak into eval inputs or few-shot files.
