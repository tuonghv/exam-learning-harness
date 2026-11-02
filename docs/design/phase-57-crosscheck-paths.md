# Phase 57 - Standard crosscheck paths
# Phase 57 - Crosscheck paths (draft for docs/design/phase-57-crosscheck-paths.md)
Task: TASK-057 · REQ-0061 (RAW-00171/172) · Status: draft
## Goal
User checks any task from committed paths only: design, report, `docs/report/evidence/TASK-NNN/` (small text),
one generated `docs/report/INDEX.md`. work/ stays raw scratch. Known when AC1-AC4 rows below pass.
## Constraints
- Roles cannot write `docs/report/*` (agent_setup.json:108, bash_deny :134): main publishes. Keep it so.
- Legacy tasks (<=056, all DONE) must not start failing workflow-check: opt-in flag like `crosscheck_required`.
- Python stdlib, Bash 3.2; no hook/settings/agent_setup change.
## Known incidents
- TASK-056: `tasks.sh commit` refused `docs/report/evidence/...` ("path(s) outside TASK scope", _tasks.py:1191 via `_path_ok` :1109).
## Plan modes
Workflow tooling only: no change to ingest, solve or pipeline plans. Gates are opt-in per task (`evidence_required`), so existing and queued tasks behave as before.

## Design
### 57.1 Convention text (owner: CLAUDE.md, docs/guide/workflow-roles.md)
- CLAUDE.md, one line under `## Workflow` list: `Crosscheck paths: docs/report/INDEX.md (generated); rule: workflow-roles.md §9.`
- workflow-roles.md new `## 9. User-facing crosscheck paths`: kinds table (copy INDEX.md:5-11), raw vs summary rule,
  who publishes (main, at VERIFIED via advance), content rules (57.4), index at DONE (57.5). §4 :61 gets "summaries: §9".
### 57.2 Opt-in flag (owner: backlog.sh:127, _tasks.py:738)
- Add `"evidence_required": True` next to `crosscheck_required` at both pick sites. Main sets it on TASK-057 by
  `tasks.sh set` (already picked). Absent key = legacy: WARN only (same pattern as workflow-check.sh:162-163).
### 57.3 Publish step (owner: new .claude/scripts/_evidence.py `publish`; caller _advance.py)
- `python3 .claude/scripts/_evidence.py publish TASK-N <src>...`: src must be under `work/TASK-N/` (evidence/ or handoff/);
  dest `docs/report/evidence/TASK-N/<basename>`; name `^[A-Za-z0-9_.-]+\.(txt|md|tsv)$`; runs `scan` (57.4) first,
  refuses all on any hit (rc 1, `FAIL: <file>:<line> <rule>`); same bytes = no-op (idempotent); prints dest paths.
- _advance.py VERIFIED: spec key `publish: [paths]` (optional; default = `verification.evidence` entries under
  `work/<T>/`). Runs publish before workflow-check (_advance.py:503), stores `verification.published: [dest...]`,
  appends dests to commit paths (:516). Add `publish` to check_schema allowed spec keys (:291) for VERIFIED only.
- Roles: unchanged location. save-evidence.sh writes `work/<T>/evidence/<name>.txt` (raw); header comment (:2-7) gains
  one line "user-facing copy: main publishes at VERIFIED (§9)". brief.sh: tester/verifier briefs (near :42) add
  `Evidence: raw via save-evidence.sh in work/<T>/evidence/; also write a <=200-line text summary there
  (no exam text/keys/URLs); main publishes it.` Handoffs test.md/verify.md are publishable as-is (054-056 precedent).
### 57.4 Content guard `scan` (owner: _evidence.py `scan <file|dir>...`)
Refuse (rule ids for tests): `binary` NUL or non-UTF-8; `ext` not txt/md/tsv; `size` >200 lines or >32 KB per file,
>20 files or >256 KB per task dir; `exam-heading` `^#{1,3}\s*(Question|Passage|Câu)\s*\d*` ;
`options` >=2 lines `^\s*[A-Ea-e][.)]\s+\S` with different letters within 6 lines; `answer-line`
`(?i)^\W*(final|correct)\s+answer\s*:|đáp án\s*:`; `answer-json` `"answer"\s*:\s*"[A-Ea-e](-[a-e])*"`;
`answer-tsv` >=3 lines `^\s*\d{1,3}[\t ,:.]+[A-Ea-e]\s*$`; `url` `https?://`; `secret`
`sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|-----BEGIN [A-Z ]*PRIVATE KEY|(?i)(api[_-]?key|password|secret|token)\s*[=:]\s*\S{8,}`.
Calibration: on current 22 files only TASK-055/qa-dryrun.txt must fail (heading/options/size); recount.tsv,
run-stats, verify.md must pass (checked by grep: no URL/secret hits; TASK-NNN does not match `sk-`, needs `\b`... use
`(?<![A-Za-z])sk-`). No exam-key source is read by scan (pure regex), so eval keys never enter it.
### 57.5 Gates (owner: workflow-check.sh, only when `evidence_required` is true)
- VERIFIED+: `verification.published` non-empty; each path under `docs/report/evidence/<T>/`, exists, not
  git-ignored (`git check-ignore -q` rc 1); `_evidence.py scan docs/report/evidence/<T>` rc 0.
- DONE: report file text contains >=1 `docs/report/evidence/<T>/<file>` and every such cited path exists;
  INDEX.md has a row starting `| <T> `.
- Committed: commit-check already fails when `docs/report` files are changed but unstaged (commit-check.sh:211-239),
  so existing + staged = committed. No new commit-check rule.
### 57.6 Scope fix (owner: _tasks.py `_path_ok` :1109; commit-check.sh :233-236)
- `_path_ok(t,p)`: also True for `p.startswith("docs/report/evidence/%s/" % t)` and `p == "docs/report/INDEX.md"`.
- commit-check multi mode `_foreign_phase_doc`: also treat `docs/report/evidence/TASK-M/...` with M != mine as foreign.
  INDEX.md stays covered (only a DONE commit rewrites it and stages it).
### 57.7 INDEX generator (owner: _evidence.py `index [--check]`; caller _advance.py DONE)
- Inputs: backlog.json (task_id, title, status, report), `task.<T>.json` design.path if present else
  `docs/design/phase-<N>-*.md` glob, report path, `docs/report/evidence/<T>/` listing, report text grep for
  `results/run-history` and `review/` paths. Rows: every backlog item with status done or an evidence dir, sorted
  by task number. Columns: Task+title (title cut 40 chars), Design, Report, Evidence (dir + file count), Run history,
  Review pack (`-` when none). Header = fixed kinds table + rule line (INDEX.md:1-11, :19).
- Deterministic: no timestamps, sorted listings, `\n` endings; writes only on change. `--check` rc 1 when stale.
- _advance.py DONE: run `index` after `backlog.sh complete` (:498-502), add `docs/report/INDEX.md` to commit paths.
## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| summary contains exam text/key/URL | publish refuses, advance VERIFIED FAIL | `FAIL: <file>:<line> <rule>` |
| report cites no evidence path (flagged task) | workflow-check FAIL at DONE | `report names no docs/report/evidence/<T>/ file` |
| evidence staged under other task in multi mode | filtered as foreign, not this commit's | nothing (correct) |
| INDEX.md hand-edited | regenerated at next DONE; `index --check` rc 1 | diff in DONE commit |
| legacy task no flag | WARN only | `WARN: no published evidence (evidence_required not set)` |
## Unit tests (tests/unit/test_evidence.py, .claude/scripts/checks/advance_test.sh)
- scan: one positive + one negative fixture per rule id; 4-line FORMAT-style option block fails; prose "Option A. and B" one line passes; `TASK-054` not a secret.
- publish: copies, idempotent second run (mtime unchanged), refuses src outside work/<T>/, refuses bad name, all-or-nothing on one bad file.
- index: two runs byte-identical; row set = done tasks; evidence count right; `--check` rc 0 after write, 1 after edit.
- _path_ok: accepts own evidence + INDEX.md, rejects `docs/report/evidence/TASK-OTHER/x`.
- workflow-check: flagged VERIFIED without published FAIL; with FAIL-scan file FAIL; DONE report without cite FAIL; unflagged WARN only.
- advance_test.sh: VERIFIED with `publish` stages dests; DONE stages INDEX.md; `tasks.sh commit` accepts both.
## Verification
| Item | command -> expected | tier |
|---|---|---|
| 57.1 | `grep -n 'INDEX.md' CLAUDE.md; grep -n '^## 9' docs/guide/workflow-roles.md` -> 1 hit each | free |
| 57.2 | `grep -c evidence_required .claude/scripts/backlog.sh .claude/scripts/_tasks.py` -> >=1 each | free |
| 57.3 | `advance.sh TASK-057 VERIFIED --dry-run` -> plan lists publish dests | free |
| 57.4 | `python3 .claude/scripts/_evidence.py scan docs/report/evidence` -> only TASK-055/qa-dryrun.txt fails (before backfill trim) | free |
| 57.5 | `workflow-check.sh --task TASK-057` PASS at VERIFIED/DONE; unit cases above | free |
| 57.6 | `tasks.sh commit TASK-057 ... -- docs/report/evidence/TASK-057/x.txt` -> no "outside" FAIL | free |
| 57.7 | `_evidence.py index && _evidence.py index --check` -> rc 0, `git diff --stat docs/report/INDEX.md` empty on 2nd run | free |
| AC4 | `_evidence.py scan docs/report/evidence/TASK-05{4,5,6}` rc 0 after qa-dryrun trimmed | free |
| tests | `python3 -I -m unittest discover -s tests/unit` -> OK | free |
## Decisions
- Main publishes via advance (roles keep no docs/report write) - rejected: widen guard for tester/verifier (needs user go, more risk).
- Opt-in flag - rejected: task-number cutoff (brittle; flag matches crosscheck_required precedent).
- Scan in workflow-check, not a new commit-check rule - avoids a new commit block; commit-check already runs the staged-tree check.
- One new file `_evidence.py` (scan/publish/index) - rejected: three bash scripts; extending save-evidence.sh (role-callable, would let roles write docs/report through a script).
## Needs user go
- None. (Not chosen: guard write grant `docs/report/evidence/{T}/*` for roles in agent_setup.json; staged-file scan in commit-check for unflagged hand copies.)
## Gaps
- G1: absolute paths (`/home/<user>/..`, `/tmp/claude-1627/...`) in outputs leak the local username; not refused (tracebacks need them). Ask user: redact on publish (replace repo root with `.`) yes/no. Recommend yes, publish-time only.
- G2: thresholds (200 lines/32 KB) are a guess calibrated on 054-056 (largest passing 126 lines); TASK-054/suite.txt 119 ok.
- G3: `options` rule may false-positive on design notes quoting `A.`/`B.` lists; publish refuses, author rewords.
- G4: TASK-057 was picked before 57.2; main must set `evidence_required` on it by hand.
## Defects
- D1 (medium, AC2/AC4): docs/report/evidence/TASK-055/qa-dryrun.txt - 380 lines, committed exam prompt dump incl. `## Question 1` (:68) and option lines (:73-75), 85 exam-pattern hits; violates the INDEX.md:19 rule. Fix: replace with a <=40-line summary (cmd, rc, prompt size, group counts), raw stays in work/.
- D2 (low): INDEX.md is hand-written (no generator), so it drifts; fixed by 57.7.
- D3 (low): `_path_ok` (_tasks.py:1109-1121) has no evidence-dir branch -> TASK-056 incident; fixed by 57.6.

Nova

## Decision (coordinator)
G1: absolute paths such as /home/<user> are redacted when publishing evidence (recommended; no user input needed).

## Revision (RAW-00174, user 2026-11-02)
- Solve OUTPUT is never tracked: default `--out` = `reports/<exam-id>/<run-id>/`, history = `reports/run-history.jsonl` (replaces `results/run-history.jsonl`; read the old path in `run-stats` for backfill), `plans/` for per-exam solve plans. Both are already in .gitignore (`reports/*`, `plans/`). Test: solve a fixture exam with no `--out`; `git status --porcelain` is empty. (57.8, owner: cli.py DEFAULT_HISTORY, solve_main default out; docs/guide/toolkit-reference.md)
- Evidence/report publish and INDEX gate apply only to BIG changes: `evidence_required` is set per task by the coordinator (engine behaviour, prompts, formats, metrics); default false; small tasks ship design + report text only. 57.2 already opt-in; no default change needed.
