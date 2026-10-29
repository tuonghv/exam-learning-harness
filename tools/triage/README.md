# inbox-triage → ReqKit

Drop a message as a file instead of typing it into a long-running session. A headless
`inbox-triage` agent turns it into Triage Records, and a deterministic adapter imports each one
into ReqKit as a **RAW prompt**. After that it follows the same path as a typed prompt: the next
session sees `[GAP] untriaged RAW` and sorts it with the `req-intake` skill (link it to a REQ,
create a REQ, or ignore it). ReqKit stays the only system of record: it owns ids, dedup, REQs and
status. Design: `docs/design/phase-71-inbox-triage-intake.md`. Mapping:
`.claude/skills/inbox-triage/references/reqkit-contract.md`.

## Run

```bash
cp note.md .triage/inbox/              # any *.md / *.txt; the first line may start with !now or @later
tools/triage/orchestrate.sh            # one pass over the inbox (paid: one Sonnet call per message)
tools/triage/orchestrate.sh --watch 60 # poll every 60 s (the only inbox watcher)
python3 .claude/req/req.py raw list --new   # the imported RAWs, ready for req-intake
```

Keep it running (the watcher itself is free; each message costs one Sonnet call, about $0.11 with the context pack):

```bash
sudo apt install inotify-tools                              # optional: instant pickup (else polls every 5 s)
nohup tools/triage/watch.sh >/dev/null 2>&1 &               # or run it in tmux; stop: kill $(cat .triage/.watch.pid)
tail -f .triage/logs/watch.log .triage/logs/orchestrate.log
```
`watch.sh` drains the inbox at start and after every drop, allows one watcher per `.triage/`,
waits `TRIAGE_BACKOFF` (900 s) after a service failure (rate limit or auth), then retries.

Exit codes: `0` pass done (some records may be invalid, see `logs/`), `3` service failure (auth,
rate limit or unreadable CLI output: the message goes back to `inbox/` and the run stops), `11`
another run holds `.triage/.lock`.

## Directory lifecycle (`.triage/`, gitignored, created on first run)

| Dir | Holds |
|---|---|
| `inbox/` | new messages (names made safe: `[A-Za-z0-9._-]`) |
| `processing/` | the message being triaged (moved with `mv`) |
| `done/` / `failed/` | triaged messages / ERROR, bad output or a write-guard breach |
| `staging/` | records from the agent, waiting for the adapter |
| `submitted/` | imported records, with `reqkit_id` (the RAW id) |
| `invalid/` | records rejected (schema, unknown target, bad id, secret, ReqKit error), with `reason` |
| `outbox/` | `<triage_id>.question.md` for the requester, plus the held record `<triage_id>.json` |
| `logs/` | `orchestrate.log`, `adapter.log`, the CLI output per message |
| `ledger.tsv` | `triage_id → RAW id`: re-running a message never creates a second RAW |

**File names.** Use a new, unique name for each message, for example
`20260929-2145-status-json-flag.md`. The name becomes the id (`trg-<name>-NN`), so a reused name
is treated as the same message and skipped as a duplicate. Characters outside `[A-Za-z0-9._-]`
become `-`, and names starting with `.` are ignored. Start the first line with `!now` (urgent) or
`@later` (low) to set the priority.

**Answering a question.** Drop a new message that cites the id, for example
`20260929-2200-reply-payments.md`: `re trg-ambiguous-01: it is the Sys/main plan`. The
orchestrator appends the held request to the agent's copy. The agent then writes one complete new
request, and the held one moves to `outbox/answered/`. If the answer is still unclear, the
agent asks again. Nothing under `.triage/` is tracked by git or cleaned up automatically: delete
`done/`, `submitted/`, `logs/` and `outbox/answered/` whenever you like, but keep `ledger.tsv`.

## How it stays safe

- The agent runs with `--tools Read,Write` in a temp dir **outside the repo** that holds only the
  skill, the contract, the context pack (docs only) and a copy of the message. So no project hooks run: ReqKit never captures the
  orchestrator's prompt, and the Stop and role guards don't fire.
- Write guard: only `staging/trg-*.json` and `outbox/trg-*.question.md` may appear, the message
  copy must stay unchanged, and `git status` of the repo must match before and after (outside
  `docs/req`). Anything else sends the message to `failed/`. Don't edit the tree while a pass runs,
  or the guard fails that message; it is safe to re-drop.
- The adapter trusts nothing from the model. It checks each record against
  `schema/triage-record.v1.json`, `known_targets.sh` (plus the contract's aliases), the id shapes
  and a secret scan, and never logs a secret value. It writes ReqKit data only through
  `req.py raw add`.

## Files

`orchestrate.sh` (Bash 3.2), `watch.sh` (always-on watcher), `context_pack.sh` (the agent's read-only
project context: CLAUDE.md, ReqKit INDEX, req-intake skill, skill/agent list, reference headings), `adapter.py` (Python 3.8 stdlib), `known_targets.sh` (`toolkit` +
`<sys>/<plan>`), `open_requests.sh` (`req.py list --active`), `tests/triage_test.sh` (scratch kit,
fake `claude`, run by `tests/run_all.sh triage`), `tests/fixtures/`.
Env: `TRIAGE_DIR`, `CLAUDE_BIN`, `TRIAGE_MODEL`, `TRIAGE_TARGETS_FILE`, `TRIAGE_REQ_CMD`, `REQ_DIR`.
