# DESIGN — `init` status: newly discovered repos need manual approval

Task: TASK-001 · Status: design approved by user (2026-09-18)

## Problem
`init_manifest.sh` adds every discovered repo as `pending`, and `scan_batch.sh`
/ `auto_scan.sh` scan anything `pending`. A repo that appears under
`REPOS_ROOT` is therefore scanned (tokens spent) without anyone deciding it is
in scope. Required: discovery produces a new `init` status, and a human moves a
repo to `pending` before it can be reviewed.

## Decisions (confirmed with user)
1. Status name is `init`.
2. Existing manifest entries are **not migrated** — the 30 `pending` / 1
   `failed` stay as they are. `init` applies to repos discovered from now on.
3. No bypass: `--force` does not scan an `init` repo.

## Status flow
```
init ──(--approve)──> pending ──> in_progress ──> done | failed
  ^                     │                           │
  └────(--unapprove)────┘         --retry-failed ───┘ (-> pending)
```
`init` is inert: no batch selection, no crash-reset, no retry touches it.

## Existing components (reuse)
- `init_manifest.sh` entry literal (lines 47, 71) — only the status value changes.
- `scan_batch.sh`: arg loop, `ONLY_WS` (`--workspace`), `acquire_lock()`
  (`.scan.lock`), `jq > tmp && mv` write idiom, `--dry-run`. Approval reuses all
  of these; no new script (invariant #4: status transitions only in `scan_batch.sh`).
- Batch selection `SELECT_FILTER='select(.status=="pending")'` already excludes
  `init` — no change for the normal batch path.
- `auto_scan.sh pending_count()` counts only `pending` — scheduler logic unchanged.

## Proposed change
| File | Change |
|---|---|
| `config.sh` | `NEW_REPO_STATUS=init` (in a "Discovery" block). `pending` restores old auto-approve behaviour. Validated to be `init` or `pending`. |
| `init_manifest.sh` | New entries use `--arg st "$NEW_REPO_STATUS"` → `"status": $st`. Existing entries untouched. Final message: count of new `init` repos + the approve command. |
| `scan_batch.sh` args | `--approve <repo>`, `--approve-all`, `--unapprove <repo>`. All honour `--workspace <ws>` (with `--approve-all` it limits to that workspace) and `--dry-run` (report only). |
| `scan_batch.sh` approval mode | Runs after the jq/manifest checks and `acquire_lock`, **before** the `claude`/`timeout` prerequisite checks (approving needs no Claude). Changes only `init`→`pending` (approve) or `pending`→`init` (unapprove); never touches `attempts` or other fields. Prints each changed `ws/repo`, then exits 0. A named repo that is not in the source status → message, no change, exit 0. A name matching repos in >1 workspace without `--workspace` → list them, exit 2. Unknown name → exit 2. Approval flags cannot be combined with `--repo`/`--retry-failed` → exit 2. |
| `scan_batch.sh` `--repo` | Currently scans a repo in any status. Refuse when the target is `init`: "not approved — run `--approve <name>` first", exit 2. `--force` does not override. |
| `scan_batch.sh` empty-batch message | When nothing is pending, also print "N repo(s) in `init` awaiting approval (`--approve`)". |
| `status.sh` | `INIT` count; progress line `init N (awaiting approval) \| done … \| pending … \| failed …`. ETA unchanged (pending only). |
| `auto_scan.sh` | Text only: queue-empty log / notification and `status` "Scan queue" line show the `init` count. No logic change, no manifest writes. |
| `summarize_report.sh` | Coverage-gap section: separate "Not approved for review: N (`init`)" block next to "Not yet scanned". |
| `CLAUDE.md`, `README.md` | Status flow, manifest schema note, command table, `init_manifest.sh` description. |

## Risks
- **Silent non-scanning**: a new repo sits in `init` forever unnoticed →
  mitigated by the count in `status.sh`, `auto_scan.sh status`, the empty-batch
  message and the report coverage-gap section.
- **Readers that enumerate statuses**: any `select(.status==…)` count that sums
  to `TOTAL` would not add up. Audited: `status.sh`, `summarize_report.sh`,
  `summarize_exec.sh`, `auto_scan.sh` — only counts, none assume the sum. The
  report's "covers X of TOTAL" wording remains true.
- **Concurrent approve while a batch runs**: approval takes the same
  `.scan.lock`, so it fails loudly instead of racing the batch's writes.
- **bash 3.2**: no new arrays/mapfile; same idioms as existing arg parsing.

## Test strategy
Unit (scratch copy of the toolkit, `REPOS_ROOT` → 2–3 `git init` dirs, fake
`claude` on `PATH`, no tokens spent):
1. `init_manifest.sh` → new entries `init`; re-run adds nothing, changes nothing.
2. `NEW_REPO_STATUS=pending` → old behaviour.
3. `scan_batch.sh --dry-run` → selects nothing while all are `init`.
4. `--repo X` on `init` → refused exit 2; with `--force` → still refused.
5. `--approve X --dry-run` → reports, manifest byte-identical.
6. `--approve X` → only X becomes `pending`, `attempts` unchanged; `--dry-run` batch selects X.
7. `--approve-all --workspace W` → only W's `init` repos change.
8. `--unapprove X` → back to `init`; on a `done` repo → no change.
9. Duplicate name in two workspaces without `--workspace` → exit 2.
10. Approve while lock held by live pid → exit 1, manifest unchanged.
11. `bash -n` + shellcheck on changed scripts.
Real verification: `status.sh`, `auto_scan.sh status`, `summarize_report.sh`
show the `init` count; a fake-claude batch after approval scans only approved repos.

## Acceptance criteria
- AC1 New repos from `init_manifest.sh` get `status: "init"` (default config); existing entries unchanged.
- AC2 No batch, `auto_scan.sh` run, `--retry-failed` or `--force` scans an `init` repo; `--repo` refuses it.
- AC3 `--approve <repo>` / `--approve-all [--workspace]` move `init`→`pending` only, under the lock, `attempts` untouched; `--unapprove` reverses; `--dry-run` changes nothing.
- AC4 `status.sh`, `auto_scan.sh status`, empty-batch message and the report show the `init` count.
- AC5 `NEW_REPO_STATUS=pending` restores the previous behaviour.
- AC6 CLAUDE.md/README document the new status and flags.
