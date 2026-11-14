# Phase 106: exam backup of the untracked rebuild inputs
Task: TASK-106 (REQ-0113 AC1-AC5)

## Goal
`exam backup` writes `<DEST>/exam-inputs-<UTCSTAMP>.tar.gz` + `<same>.sha256.json` (manifest) holding `plans/`, `input/`,
`config/published_reports.json`, verified after writing, newest N kept. `exam backup --check A [--restore-to D]` proves an
archive is intact and restores it so `exam rebuild-reports --dry-run` on D finds every recipe input. Nothing leaves the machine.

## Constraints
- Reuse: `plansmigrate.make_backup` (src/exam_engine/pipeline/plansmigrate.py:713) = inside-root refusal (:717-720),
  free-space check with `MIN_FREE` (:30, :724-728), tar.gz write + listing re-read (:731-741), `_sha_file` (:77). Extract, no 2nd copy.
- Archive members are repo-relative (`plans/...`, `input/...`, `config/published_reports.json`) so recipe paths
  (phase-105 §105.1 `plan_runs`, `key`) resolve unchanged under a restore root.
- Keys (input/*.answer.txt) only go to DEST on the local disk; no network, no upload code.
- Generality: no exam literal; the three roots are a module constant `BACKUP_ROOTS`; test tree is a synthetic non-DGNL exam.

## Known incidents
none

## Plan modes
none: no solve/pipeline input changed (read-only over plans/ input/ config/).

## Design
### 106.1 Extract shared tar helpers (owner: new src/exam_engine/pipeline/tarbackup.py)
- `refuse_inside(dest, root) -> str` realpath of dest; ValueError if dest == root or under root (moved from :717-720).
- `ensure_free(dir, need_bytes)` makedirs + `shutil.disk_usage` check, need = bytes + MIN_FREE (moved from :724-728; MIN_FREE moves here, plansmigrate imports it).
- `write_verified(path, items[(abs, arcname)]) -> {"members", "bytes"}` writes to `path + ".part"`, re-reads, checks count+bytes, `os.replace` to path; on mismatch deletes .part, ValueError (from :731-741).
- `sha_file(path)` = current `_sha_file` (plansmigrate keeps `_sha_file = tarbackup.sha_file` alias).
- `make_backup` keeps its signature and output dict; becomes a thin caller. Test: existing tests/unit/test_plansmigrate.py unchanged and green.

### 106.2 `exam backup` write (owner: src/exam_engine/backup.py `backup_main(argv)`; cli.py:26 list + cli.py:1678 table)
Flags `[--dest DIR] [--keep N] [--repo P]` (DIR default `~/exam-harness-backup`, N default 5, >=1; --repo default repo root, for tests).
Steps: refuse_inside(DIR, repo) -> exit 2 `ERROR: dest inside repo`; collect regular files under BACKUP_ROOTS (sorted, skip
symlinks with a WARN line, missing root = WARN, all missing = exit 2); ensure_free(DIR, sum bytes) -> exit 2;
write_verified; manifest `{"version":1,"created_utc","repo","archive","archive_sha256","files":{arcname: sha256},"bytes"}`
written atomically beside it. Prints `backup <path> files N bytes B sha256 <12>`.
Test: tmp repo (plans/x1 run, input/k.answer.txt, config/published_reports.json) -> exit 0, archive + manifest exist, manifest files == tree shas.

### 106.3 Verify after write (owner: `verify_archive(archive, manifest) -> list[str] problems`)
Open r:gz, for every file member stream-hash content; problems: sha mismatch, member missing from manifest or vice versa,
archive sha != `archive_sha256`, unsafe member (106.5 rule). backup runs it right after writing; problems -> delete archive+manifest, exit 1.
Test: monkeypatched sha in manifest -> exit 1, no archive left in DEST.

### 106.4 Rotation (owner: `_rotate(dest, keep)`)
After a verified write, list `exam-inputs-*.tar.gz` in DEST (own name pattern only, other files untouched), sort by name
(UTC stamp), delete all but newest N with their `.sha256.json`. Test: 7 dated dummy archives + `other.txt`, keep 5 -> 5 left, other.txt kept.

### 106.5 `--check ARCHIVE [--restore-to DIR]` (owner: `check_main`)
Manifest = `ARCHIVE` with `.tar.gz` -> `.sha256.json`; missing -> exit 2. verify_archive -> problems printed, exit 1; else `OK <n> files`.
Restore: DIR must be empty or absent and outside the repo (refuse_inside) else exit 2; reject the whole archive (exit 1,
nothing extracted) if any member is not a regular file or dir, has an absolute name, `..` part, or resolves outside DIR;
then extract member by member via `tf.extractfile` + write (no `extractall`, no mode/owner bits beyond 0o644/0o755).
Test: tar with `../evil`, `/abs`, a symlink, a device -> each exit 1 and DIR empty; good archive -> tree shas == manifest.

### 106.6 Guide (owner: docs/guide/report-kinds.md, 3-4 lines under `## How to rebuild reports` from TASK-105, after `## Commands` :46)
`exam backup` after each publish; `exam backup --check <archive>`; restore with `--restore-to` then `exam rebuild-reports --dry-run`
there; copy the archive + .sha256.json to another disk or cloud storage you own (keys are inside: keep it private).

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| DEST inside repo | exit 2, nothing written | `ERROR: dest ... inside repo` |
| low free space | exit 2, nothing written | `ERROR: not enough free space ... need/have` |
| write/verify mismatch | .part / archive + manifest removed, exit 1 | `ERROR: verify failed: <first problem>`, older archives intact |
| crash mid-write | only `.part` left; rotation ignores it | next run overwrites nothing old |
| tampered archive on --check | exit 1 | `FAIL: <member> sha mismatch` |
| unsafe member on restore | exit 1, nothing extracted | `FAIL: unsafe member <name>` |
| restore DIR not empty / inside repo | exit 2 | `ERROR: restore dir ...` |

## Unit tests (tests/unit/test_backup.py, tmp trees only, never the real plans/)
106.1 plansmigrate tests unchanged; 106.2-106.5 as listed per item; plus `--keep 0` -> exit 2.

## Verification (main runs; $0)
| Item | command -> expected |
|---|---|
| 106.1 | `python3 -I tools/run_tests.py --affected` -> test_plansmigrate PASS |
| 106.2 | `exam backup --dest ./tmpb` -> exit 2; `exam backup --dest <scratch>/eb` -> exit 0, ~34 MB archive + manifest |
| 106.3/5 | `exam backup --check <scratch>/eb/<a>` -> OK; copy, flip one byte -> exit 1 |
| 106.5 AC3 | `--restore-to <scratch>/er`, then `rebuild-reports --dry-run --root <restore dir> --recipe <restore dir>/config/published_reports.json` -> exit 0, 3 exams, no ERROR |
| 106.4 | 6 runs with --keep 5 -> 5 archives |
| 106.6 | grep `exam backup` + "another disk" in report-kinds.md |

## Decisions
- Separate `tarbackup.py` over importing plansmigrate privates: backup must not depend on migration code.
- Per-file sha manifest over archive sha only: names the damaged file on --check.
- Reject whole archive on one unsafe member over skipping it: a restore must be complete or nothing.
- reports/ not archived: it is rebuild output (TASK-105).

## Out of scope
Off-machine copy, encryption, scheduling, incremental backups.

## Defects
- D1 low, brief vs work/TASK-105/handoff/design.md:15,20: brief calls config/published_reports.json git-ignored; 105 makes it a
  tracked recipe (paths + sha only). Archiving it anyway is harmless and keeps the restore self-consistent.
- D2 low, risk for AC3: 105 must resolve recipe-relative paths (`plans/...`, `input/...`) against cwd or `--recipe`'s repo root,
  not a fixed repo constant; else the restore dry-run checks the live tree. Resolved: TASK-105 has `--root DIR` (recipe paths resolve under it, refused if they escape).

