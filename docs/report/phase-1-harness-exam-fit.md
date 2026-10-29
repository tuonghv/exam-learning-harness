# Report: TASK-001 harness fit to the exam domain (REQ-0005)

**Verdict: adopted.** Scan-era text, skills, roles and files are removed or compressed; subagent management and monitoring are kept.

## Task and requirement
Fit the cloned security-scan harness to the exam/learning purpose (REQ-0005, AC1-AC13). Design: `docs/design/phase-1-harness-exam-fit.md`.

## Implementation (commits)
- A: `CLAUDE.md` rewritten to the exam purpose, 9,200 -> 3,967 B.
- B (`097a49c`): `docs/guide/exam-brief-override.md`, crosscheck "Exam content oracle", verify Tier-1 content note, command and `workflow-roles.md` pointer cleanup, `lead` role deleted.
- C (`48454fd`): 15 skills, 2,066 -> 794 lines (limit 1,033); 12 scan-era skills removed earlier.
- D (`eb2f41b`): role bodies 646 -> 326 lines, each 57-71 (limit 75); markers kept.
- E (`fa21894`): `tools/triage`, `lessons.py` with its two tests and ledger, three stale docs, triage `.gitignore` lines removed.
- Earlier: 18 dead `ask` rules removed from `settings.json` (`e37cc92`).

## Reuse
Kept the workflow, req-kit, gates, coordinator, role-monitor, inspector, `team-status.sh`, `watch-role.sh`, `brief.sh`. Untouched (AC11): `agent_setup.json`, `agent_setup.py`, its test.

## Tests and verification
- Tester (`work/TASK-001/handoff/test.md`): AC1-AC13 read-only checks, all PASS.
- Verifier (`work/TASK-001/handoff/verify.md`): VERIFIED, none REFUTED; AC4, AC5, AC11 were run by the coordinator with git (observed by the coordinator: empty diff since 5e05abd, AC5 grep empty).

## Limitations
- `tools/examples/*` is named in `CLAUDE.md` and role bodies before REQ-0002 creates it.
- `brief.sh:85,96,99` and `workflow-check.sh:317` still name removed things (left on purpose, not edited).
- `tools/inspect/INDEX.md` and the `lead_*` tests remain; removal needs the user's OK.
- The text inside the `agent-setup:project` blocks of four role bodies was edited (scan rules replaced); the hook writes that block only on `init --profile`.
- The step D coder's `cp` into `.claude/agents/*` passed the guard that should block role writes; the guard was not changed.
- Coder role waived: its handoffs are PARTIAL; the coordinator finished steps B-E.

User instructions honoured: RAW-00017, RAW-00018, RAW-00019, RAW-00020, RAW-00022, RAW-00023, RAW-00025 (RAW-00025 is new EPIC-003, not part of this task)
