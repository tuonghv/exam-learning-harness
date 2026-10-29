# ReqKit Integration Contract

Filled from ReqKit (`.claude/req/req.py`, data in `docs/req/`) on 2026-09-29 (TASK-071,
design `docs/design/phase-71-inbox-triage-intake.md`). The triage agent reads it to adopt
ReqKit vocabulary; `tools/triage/adapter.py` implements it.

## 1. Ownership

| Concern | Owner |
|---|---|
| Watching the raw inbox | triage orchestrator (`tools/triage/orchestrate.sh`); ReqKit watches no directory |
| Canonical request schema | ReqKit (RAW → REQ/EPIC files under `docs/req/`) |
| Request ID generation | ReqKit (`RAW-NNNNN`, `REQ-NNNN`, `EPIC-NNN`) |
| Deduplication decision | ReqKit (`req-intake`: link RAW to an existing REQ, or create one) |
| Canonical queue / state transitions | ReqKit (`req.py status`, TODO → … → DONE) |
| `.triage/` directory | inbox-triage |

## 2. Entry point

- Submit: `python3 .claude/req/req.py raw add --text "<rendered record>"`. One record = one RAW
  with status `NEW`. ReqKit then treats it exactly like a typed prompt: a session sorts it
  with the `req-intake` skill (link / new REQ / ignore with reason).
- Validation ReqKit provides: none at RAW level (it stores text verbatim, truncated at 20000
  chars). The adapter validates against `tools/triage/schema/triage-record.v1.json` first.
- Created ID: printed alone on stdout (`RAW-00140`). That is the `reqkit_id`.

## 3. Field mapping

| Triage Record field | ReqKit field | Transform |
|---|---|---|
| `title` | RAW body, line 2 | verbatim |
| `task` | RAW body, paragraph after the title | verbatim |
| `category` | RAW header line (REQ `area` is chosen at intake) | label, value map below |
| `priority` | RAW header line (ReqKit has no priority field) | value map below |
| `target` | RAW header line `target <t>` | alias map below, must be in KNOWN_TARGETS or null |
| `acceptance` | RAW body `Acceptance:` list | verbatim; becomes REQ Acceptance at intake |
| `context_refs` | RAW body `Context:` line | `file:lines`, comma separated |
| `related_reqkit_id` | RAW body `Relates to: <id> (<intent>)` | `req-intake` applies it (`raw link --to REQ-…`) |
| `possible_duplicate_of` | RAW body `Possible duplicate of:` (REQ/RAW/EPIC ids) and `Answers held request:` (`trg-…` ids) | ids only; the adapter marks the answered held request done |
| `needs_clarification` | not submitted | record held in `.triage/outbox/`, question to requester |
| `triage_id` | RAW header line + local ledger `.triage/ledger.tsv` | idempotency key (ReqKit has no external-ref field) |

Open request ids in `OPEN_REQUESTS` are REQ ids (`REQ-0028`). An `update`/`cancel` must cite one.

Reply to a clarification: a message that cites a held `trg-…` id is **not** an `update` (a held
request has no ReqKit id yet). Emit intent `new`, merge the held request (the orchestrator appends
it to the message as `--- Held request trg-… ---`) with the answers into one self-contained record,
and put the cited `trg-…` id in `possible_duplicate_of`. If the answers still leave the target or
the task unclear, ask again (`needs_clarification: true`). `update`/`cancel` always need a REQ id
from `OPEN_REQUESTS` in `related_reqkit_id`; without one, use `new` or `question`.

## 4. Value maps

Priority: `urgent` → `URGENT`, `normal` → `-`, `low` → `low`

Category (label only): `scan` → `scan`, `fix` → `fix`, `review` → `review`, `config` → `config`,
`investigate` → `investigate`, `other` → `other`

## 5. Target aliases

```
# alias -> canonical target
scanner -> toolkit
code-security-scanner -> toolkit
security-scanner -> toolkit
```
Canonical targets: `toolkit` (this repo) and each review plan `<sys>/<plan>` under `plans/`
(`tools/triage/known_targets.sh`).

Default target: when the message names no target and is about this project itself (its
scripts, reports, pipeline, scans as a feature, ReqKit / "req kit", triage, agents, skills,
hooks, tests or docs; see `context/project.md`), the target is `toolkit`. Ask only when the
message points at a system, service or repo that is not in KNOWN_TARGETS (for example "the
payments service"), or when it asks for a scan without saying which plan.

## 6. Coexistence rules

- ReqKit's own intake skill and inbox-triage must not both trigger on the same message.
  Resolution chosen: ReqKit's `req-intake` sorts prompts typed into a session (captured by its
  UserPromptSubmit hook) and every RAW the adapter imports; inbox-triage runs only headless
  from the orchestrator, outside the repo (no project hooks, so its prompt is never captured),
  and its skill has `disable-model-invocation: true`.
- Reserved prefixes/markers already used by ReqKit (to avoid reuse): ids `RAW-`, `REQ-`,
  `EPIC-`; RAW statuses `NEW`, `TRIAGED`, `IGNORED`; REQ statuses `TODO`, `DESIGN`,
  `IMPLEMENTING`, `UNIT_TESTED`, `VERIFIED`, `DONE`, `SUPERSEDED`, `REJECTED`; hook output
  prefixes `[REQ]`, `[GAP]`, `[WARN]`; lock file `docs/req/.lock`.
