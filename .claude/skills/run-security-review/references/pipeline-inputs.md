# Pipeline inputs: where each step gets its data (phase 124.9)

One row per catalog feature (`features.conf`; drift test `tests/features_catalog_test.sh` S1 fails when a row is missing).
State of every feature for a plan, $0: `./plan.sh features <system>/<plan>` (`--all` for the catalog); run snapshot: `<run_dir>/features.json`.
Product records live in `products.conf` (kinds `deploy`, `gateway`, `exposure`, `logreach`; `products_check` in `products_common.sh`, run by tests/features_catalog_test.sh P1).
Never put link values or log contents in notes or replies: counts and key names only.

Deploy source order (pipeline.sh deploy step): CLI `--from-dir` > products.conf `deploy` record (provider) > `PIPELINE_DEPLOY_DIR` > `kubectl` > none.
A product with a deploy record never falls back to `kubectl` or `PIPELINE_DEPLOY_DIR` (the 122.10 gate holds an empty context). `PIPELINE_DEPLOY_PROVIDER=0` switches the record off. Stuck-case history: `docs/notes/deploy-context-stuck-2026-10-18.md`.
Logreach order: `LOGREACH_PROFILE` (plan.conf/env) > products.conf `logreach <P> profile=` > off (`off` = off; unset = missing).

| feature | step | input | source order | $0 check | bad looks like | fix at product level |
|---|---|---|---|---|---|---|
| core | phase0, graph, correlate, phase2b, overlay, conclude, report | plan repos under `REPOS_ROOT` | plan.conf / manifest | `./pipeline.sh run --dry-run` | a path that is not a repo of the plan | fix the plan (`./plan.sh`), not the tree |
| deploy | deploy | product `deploy` record (link, alias, active list, edges) | `--from-dir` > `deploy` record > `PIPELINE_DEPLOY_DIR` > `kubectl` > none | `./pipeline.sh status` deploy line; `check_deliverables.sh --run latest` D16 | `source=none`, empty verdict, 0 edges, WARNING "no kubectl, no --from-dir and no deploy record" | add or repair the `deploy` record in products.conf, then `./pipeline.sh new`; one-off `./pipeline.sh run --from-dir DIR` |
| recon | recon, gate | repo trees (read by the headless review call only) | plan repos | `./pipeline.sh status` | gate step waiting with no approval | approve at the gate; no product input |
| extpre | extpre | repo trees via pinned tool containers | `EXT_SCAN` | `./plan.sh features <sys>/<plan>` (state off/on) | state off while tools were expected | set `EXT_SCAN=1` in plan.conf |
| phase1 | phase1 | repo trees, cards | `REVIEW_AI` | `./pipeline.sh status` | `REVIEW_AI=0` on an AI plan, 0 cards | set `REVIEW_AI=1`; tools-only plans keep 0 |
| inventory | - | plan `ACTIVE_APPS_LIST` | plan.conf `ACTIVE_APPS_LIST` > env > empty | `./plan.sh features <sys>/<plan>` (missing=warn) | state missing: no active-app list, every repo counted active | set `ACTIVE_APPS_LIST` (or the deploy record `active=`) |
| checkpoints | cp1, cp2b | run state | `PIPELINE_CHECKPOINTS` | `./pipeline.sh status` | run stops at a checkpoint nobody expected | answer the checkpoint or set the switch off in plan.conf |
| verify | verify | phase 2b results | `PIPELINE_VERIFY` | `python3 coverage_check.py <run_dir> --conclusion` | gaps > 0, verify step skipped | enable the switch and re-run the step; never edit results |
| logreach | logreach | product `logreach` record (profile) and Elasticsearch | Logreach order above | `./plan.sh features <sys>/<plan>`; `check_deliverables.sh --run latest` D15 | state missing "LOGREACH_PROFILE not set", or `logreach.json` status unavailable | add `logreach <P> profile=<name>` to products.conf; check Elasticsearch reach outside the toolkit |
| ext | ext, toolsp1 | repo trees via tool containers | `EXT_SCAN` | `./plan.sh features <sys>/<plan>` | no `ext_ab_<date>.md`, tools-only report empty | `EXT_SCAN=1`, see skill `ext-scan` |
| gapreview | gapreview | tool findings with no AI match | `EXT_GAP_REVIEW` (default 0) | `./plan.sh features <sys>/<plan>` | expected gap review absent (switch off) | set `EXT_GAP_REVIEW=1` (paid) |
| tracking | - | finished run | `TRACK_AFTER_RUN` | `./plan.sh features <sys>/<plan>` | no `reports/<sys>/<plan>/tracking/<run>/index.md` | `TRACK_AFTER_RUN=1` or `PLAN=<sys>/<plan> ./tracking/track.sh --run latest` |

Two plans of one product behave differently? Compare with a working sibling: `./plan.sh compare <system>/<plan> <system>/<sibling>`.
