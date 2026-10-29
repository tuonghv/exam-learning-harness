---
name: security
description: Apply application and tooling security checks during design, implementation and verification.
---

# Security

When relevant check:
- authentication/authorization
- input validation
- injection
- command execution
- secrets
- path traversal
- SSRF
- unsafe deserialization
- sensitive data exposure
- insecure defaults
- dependency risks
- error/log disclosure

For security-sensitive changes:
1. identify threat and trust boundary
2. validate controls
3. add regression tests
4. verify resistant behavior

Do not report a vulnerability without evidence.

Run `.claude/scripts/checks/secrets.sh` (free, zero-dependency heuristic
scan for hardcoded keys/passwords) - it warns rather than blocks, since it
can false-positive; use it as a tripwire, not proof of safety.

Record the outcome in `.claude/state/task.json` under `security`:
`status` = `completed` (checks applied) or `not_applicable` (no security-relevant surface), plus `result`.
