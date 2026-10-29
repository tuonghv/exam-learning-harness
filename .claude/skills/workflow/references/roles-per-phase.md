# Workflow — roles per phase

Part of skill workflow; core rules in ../SKILL.md.

## Skills per phase — roles

The roles are required: hand every step to its role without being asked. The coordinator does
only the bookkeeping, the gate scripts, commits and paid runs (the `tester` re-runs the checks); a skipped role needs a recorded waiver. `task.json` `roles.{designer,coder,verifier}` (tester
optional) = the handoff path under `work/<T>/handoff/` with line 1 `PROGRESS: COMPLETE` and line 2
`SKILLS: ...`, or `{"waiver": "<reason>"}`; `workflow-check.sh` fails DESIGN (designer), IMPLEMENTING/UNIT_TESTED
(coder) and VERIFIED (verifier) without it, for tasks picked with `roles_required`. Grants: `roles.grants.<role>`
= a list of `protect.grantable` globs. Brief
format, keeping the roles working together, a stuck role, and alerting the user: skill `coordinator`.

Role entry points: `/next` (advance the active task), `/design-phase` (design only),
`/verify-phase` (verification, security and DONE). They load these skills for you.
