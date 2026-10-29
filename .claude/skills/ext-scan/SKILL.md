---
name: ext-scan
description: Run, debug and extend the external open-source scanners (set B: opengrep, semgrep, gosec, govulncheck, bandit, psalm, bearer; codeql bench-only; osv/gitleaks removed) through ext_scan.sh or the kit compose file external/ext-scan/docker-compose.yml, read their output and the A/B mapping report, and root-cause a failing tool. Load when asked to run a tool on a repo or tree, show tool output, add or pin a tool, fix a tool error, or reuse kit scripts/prompts/rules. $0 (Docker only, no Claude calls). Not for the paid AI scan (run-security-review).
---

# ext-scan (set B, $0)

User rules (REQ-0035, REQ-0037; RAW ids in brackets):
- Scope is OWASP API flaws reachable via an API (security_prompt.md categories) [RAW-00183]. Secrets-only tools are low priority [Q4].
- **Never drop a tool or rule without output evidence** of no value and noise; label noisy rows, keep them [RAW-00185/186].
- Show the user the tool's own output when asked; they want to see output first, then judge value [RAW-00184/187].
- Report scripts stay as they are; the deterministic layer (ext_normalize/ext_match/ext_report) does the work [RAW-00181].
- Root-cause every tool error (config, image, argv, permission) before reporting; search the web when stuck [RAW-00182/00200/00201].

## Where things live
| What | Path |
|---|---|
| Runner (plan mode) | `PLAN=<sys>/<plan> ./ext_scan.sh --stage all\|tools\|match\|report [--tools X] [--force]` |
| Tool table, argv, entrypoints | `ext_tools.sh`; config `ext/ext.ini` (parsed, never sourced); pins `env.lock` |
| Our rules | `ext/rules/api/{generic-owasp,sast-extra,go-api}.yaml` (opengrep only; semgrep runs `p/owasp-top-ten`) |
| psalm configs | `ext/psalm/psalm.xml`, `psalm-laravel.xml` |
| Per-repo output | `plans/<sys>/<plan>/results/ext/repos/<key>/{status.json,b.jsonl,b_out.jsonl,match.json,findings.md}` |
| Report | `reports/<sys>/<plan>/ext_ab_<date>.md` (Tool status, Tool findings, Mapping) |
| In-scope outputs (TASK-085, $0) | `results/ext/findings_ext.json` (one record per finding, stable id, trust-order base), `snippet_hashes.json` (hashes only); `ext_inscope_pre_<date>.md` / `ext_inscope_<date>.md` / `ext_vs_ai_inscope_<date>.md` (`ext_inscope.py`, masked snippets from `ext_snippet.py`) |
| Local copies for the user (gitignored) | `external/ext-scan/results/plans/<sys>/<plan>/<repo>/<tool>/{findings.jsonl,raw/}` [RAW-00194] |
| Kit (reference, English README) | `external/ext-scan/`; local edits listed in `IMPORT.md` "Local changes" |
| Kit reuse index | `docs/notes/ext-scan-kit-index.md` |
| Public bench corpus | `$CLAUDE_JOB_DIR/tmp/bench/<lang>/<app>`, answer key `work/TASK-076/bench/ground_truth.json` |
| Whole flow (where B sits, both modes) | `docs/guide/architecture.md` |
| Engine ($0) | `ext_engine.py compile <ext_root>` -> `conclusion_ext.json` (EXTF records, decision in/needs_ai/out, coverage rc 1); maps `ext/engine/{tools.json,api_map.json}`; run by `ext_scan.sh --stage match` before `ext_match.py` |
| Gap review (paid, not this skill's $0 scope) | `REVIEW_AI=1 [EXT_GAP_ARM=A\|B] ./ext_gapreview.sh` (unset = A, the chosen solution; B only when set; Bearer <= 30% of a repo's gap items, api_map gap.tool_max_share) -> `<ext_root>/gapreview/<arm>/conclusion2.json`; view + reports `./ext_gap_report.sh`; A/B `./ext_gap_eval.sh --dry-run\|--go`; user go + cap first |
| CodeQL | own compose `ext/codeql/docker-compose.yml` + `ext/codeql/run-codeql-tree.sh`, manual, not in `ext_scan.sh`; OSI code only |

Env: `EXT_TOOLS=all` (adds comparators), `EXT_DB_DIR=$HOME/.cache/code-security-scanner/ext-db`,
`EXT_KEEP_SCRATCH=1` keeps raw tool output (may hold code or secrets: public corpus only).

## Data rules (never break)
- Upzi (user RAW-00267): never propose, estimate or ask about paid Upzi steps (AI scan, gap review); the user asks when the engine is stable. Upzi = $0 ext-scan learning only; paid tests only on small project groups (bench).
- Source is read only inside the containers via a read-only mount. Never read `$REPOS_ROOT`,
  `pentest_source_code*` or Upzi trees yourself; list names/sizes only.
- For client/private trees store only rule, CWE, severity, path, line. Raw tool JSON/SARIF (snippets,
  secret text) goes to a `chmod 700` scratch dir and is deleted, including after a stop: check
  `/tmp/tmp.*` for leftovers. Root-owned files: `docker compose ... run --rm fixperms -R uid:gid /out`.
- Kit compose: always `export REPOS_ROOT=/nonexistent` (the semgrep service mounts it otherwise).
- **CodeQL: OSI open-source code only.** Company code needs a paid GitHub Advanced Security / Code
  Security licence; "internal only, no CI" does not change that [RAW-00202/00211]. Bearer (ELv2) is fine internally.

## Kit compose commands
```bash
F=external/ext-scan/docker-compose.yml; export REPOS_ROOT=/nonexistent REPO_DIR=<app> EXT_OUT=<dir> && mkdir -p $EXT_OUT
docker compose -f $F run --rm -w /src gosec -fmt=json -out=/out/gosec.json ./...
docker compose -f $F run --rm -w /src bandit -r . -f json -o /out/bandit.json -q
docker compose -f $F run --rm -w /src semgrep scan --metrics=off --config p/owasp-top-ten --json -o /out/semgrep.json .
docker compose -f $F run --rm -w /src -v $PWD/ext/rules:/trules:ro opengrep scan --no-git-ignore --config /trules/api --json -o /out/og.json .
docker compose -f $F run --rm -w /src bearer scan /src --format json --output /out/bearer.json --exit-code 0 --quiet
docker compose -f $F run --rm --user $(id -u):$(id -g) --entrypoint sh codeql -c 'codeql database create /tmp/db --language=<lang> --source-root=/src -q && codeql database analyze /tmp/db codeql/<pk>-queries:codeql-suites/<pk>-security-extended.qls --threads=0 --format=sarif-latest --output=/out/codeql.sarif'
```
CodeQL has its own compose `ext/codeql/docker-compose.yml` + tree runner `ext/codeql/run-codeql-tree.sh` (guide `docs/guide/codeql-open-source.md`; JDK in image, Java on an in-container copy, codeql symlink not PATH).
CodeQL: `<pk>` = javascript for `javascript-typescript`; Go needs `--build-mode=autobuild`, Java `--build-mode=none`; no PHP.
Tree script (summary rows only, raw deleted): `work/TASK-076/bench/run-compose-demo-secu-all.sh`.

## Known root causes (check these first)
| Symptom | Root cause | Fix |
|---|---|---|
| semgrep exit 127 `exec: "scan"` | image has no ENTRYPOINT (CMD `semgrep --help`) | `--entrypoint semgrep` |
| gosec "No packages found" | no `-w /src` | always `-w /src` |
| opengrep 0 rows on py/php/js | rule gap, not config | add rules to `ext/rules/api/`; Java has no local rules yet |
| psalm crash "class storage for soapfault" | `--init` scans nested `*/vendor` | own `psalm.xml` ignoring `vendor`, `*/vendor` |
| psalm 0 rows on Laravel | `$request->input()` not a source | `psalm/plugin-laravel` (^3 needs Laravel 11+, else ^2 with Psalm 5) |
| Psalm 5 crash "null as array offset" | PHP 8.5 (composer:2 base) | php:8.3-cli base |
| psalm "bad or missing SARIF" after a fix | env.lock still pins the old image id | re-pin the image id in env.lock |
| osv exit 128 | package.json without lockfile | `--allow-no-lockfiles` (status empty) |
| bearer rc=1 "dubious ownership" | root in container, host-owned /src | GIT_CONFIG_* safe.directory `*`, or run as host uid |
| bearer "0 rules found for supported language" | no source files in the tree | tree problem: tell the user |
| codeql ~12 min instead of ~15 s | bundle files root-only; non-root cannot read precompiled .qlx | `chmod -R a+rX /opt/codeql` in the image |
| bandit rc=1 | normal: bandit exits 1 on findings | none |
| danog/psalm `--init` + `psalm` | init crashes on nested vendor; no taint flag; rw mount; `:latest` | use our psalm step |

osv and gitleaks are out of the tool set (REQ-0037 Decision: tool set); chosen set = ext_tools.sh:10, comparators :11.

## Scope contracts and gates (REQ-0037 decisions; design phase-79 §79.10-79.11)
Gate order, one owner each: tool config (pre-filter, `EXT_PREFILTER=0` = unfiltered bake-off) -> normalize (no row cap; every
raw row ends in b.jsonl or b_out.jsonl) -> classify (removed/disabled/unknown tool -> `out:tool_removed`; rule table by meaning
first, CWE fallback; SCA always `dependencies`, govulncheck `reach=symbol` -> needs_ai, else out) -> scope decision in/needs_ai/out
with security_prompt.md:252-349 narrowing (one rule in >=3 functions -> `out:rule4_systemic`) -> cluster/dedupe (2 before / 5 after)
-> ext_match -> gap select (SAST/taint before SCA, per-tool quota, each item carries the category scope question).
- Tool set: osv and gitleaks removed (user, after evidence: docs/notes/osv-value-review-2026-10-01.md). Pre-filter only ids in
  "Do not report"/rule 4 with 0 bench true hits; those ids stay `out:*` in api_map. Golden set: tests/fixtures/ext_contracts/.
- Before any paid gap review: `REVIEW_AI=1 PLAN=.. ./ext_gap_eval.sh --prepare` (0 calls) and check
  `cat <ext_root>/gapreview/*/units/*/items.json | jq -r '.[]|"\(.tools|join("+"))\t\(.category)\t\(.decision)"' | sort | uniq -c`:
  no removed tool, no SCA classed by CWE, mostly SAST. The user cross-checks before "go arms".
- Gap review prompt `ext/prompts/gapreview.md` is static (prompt cache; per-unit values in params.json; findings only in
  items.json/a_list.json, never inline). Read boundary: stay in the finding's file, grep/glob with limits, windowed reads.
  Audit trail kept per call: `<ext_root>/gapreview/<arm>/units/<unit>/{prompt.md,prompt.sha256,params.json,items.json,a_list.json,answer}` + `prompts.md`.
- Phase-1 refusals on deliberately vulnerable training apps (govwa, crAPI): the output-side safety classifier cuts the report while
  writing the required attack_scenario; the job holds after the first refusal. Never work around it; report it.

## Current state and resume point (2026-10-05, design §79.16-79.19)
- Ext role is per plan (RAW-00327): keep it on big plans with the AI; turn it off for a plan only after a full scan shows the AI
  covers all and ext rows are all FP. Monthly tools-only = only NEW findings, via the one company registry, source=tools, ids `VNW-SEC` (79.17, 81.3).
- Standard (AC5, 2026-10-05): no AI review of ext rows. ext_ab_<date>.md/.pdf opens with the $0 tool summary + anomaly flags S1-S4
  (79.18, `ext_anomaly.py`); a flagged repo gets a re-review recommendation, never an automatic paid call. PL plans run the $0
  `extpre` step before the approval gate (79.19). Default re-scans every run; `EXT_SKIP_UNCHANGED=1` skips an unchanged tree hash.
- The gap review below (79.7) stays in code, off and out of the flow; history only.
- Gap review audit (RAW-00324/00326): 22/28 arm A rejections code-grounded; 4 budget-limited; input lacked rule_desc/fn_line (fixed
  442544a); ext gap prompt now greps all callers of a shared helper before `rejected`. Calibration 16.3 PASS 7/7 (1c7024a).
- Noise rules: weak HASH is noise only on cache/fingerprint/checksum paths (QA-79.10-2, govwa MD5 password kept); weak random
  keeps the path rule with user/account/profile counted as auth.
- No verdict memory / blacklist (RAW-00323) until calibration passes (≥ 6/7 covered_by_ai controls not rejected).
- Re-scan after a normalizer change: `ext_scan.sh --stage all --force`; an old gapreview conclusion then FAILs the id check (stale).

## Lessons from the bench gap review and Upzi learning (2026-10-01)
- Results and cost: docs/notes/gap-review-bench-2026-10-01.md (arm A $0.55 for 52 items; set A $1.14). Arm A is the chosen solution.
- Three-way comparison and decision (phase 1 / + hints / + gap review): docs/notes/ext-ai-comparison-2026-10-02.md. Standard = phase 1 without hints + gap review in the phase-1 schema; hints off by default.
- Any change to the ext flow or the chosen standard updates docs/guide/architecture.md in the same commit (RAW-00299; skill `commit`).
- `ext_scan.sh --tools <subset>` re-normalizes only those tools and DROPS the other tools' rows per repo (F-79-19, fix pending):
  never run a subset on a real plan; use a scratch copy or the full tools stage.
- Never edit ext_scan.sh/ext_tools.sh while a run uses them (bash reads scripts lazily).
- Tune noisy rules from the AI's rejection reasons (Bearer NoSQL -> needs_ai, Bearer cap 30 %); learn on big trees from result counts only.

## Phase-1 hints experiment (REQ-0037 RAW-00274..00279; bench only, user decides on adoption)
- `EXT_PHASE1_HINTS=1 ./scan_batch.sh` appends ONE line (ext/prompts/phase1_hints.md) after the byte-identical security_prompt.md and
  passes `ext_hints.json` (in-scope ext rows: category, cwe, rule, tool, file, line; no code, no verdict) in an extra --add-dir.
- The line must say WHERE the file is (run 1 named it without a location and the model likely never read it). Verify reads with
  `EXT_KEEP_HINTS=1` (file atime after mtime). Compare with `ext_hints_compare.py` (findings, key hits, hint outcomes, cost, quality).
- $0 scan_batch forms go through `./scan_admin.sh` (no paid prompt).

## OWASP Top 10 reference (label and crosswalk only; scope stays the 18 API categories)
- Drop the MITRE CWE view XML in `ext/reference/` (gitignored; e.g. 1450.xml = OWASP Top Ten 2025), run
  `python3 ext_ref_owasp.py ext/reference/<view>.xml` -> `ext/engine/owasp<YYYY>_cwe.json`, point `OWASP_TOP10_MAP` in ext/ext.ini
  at it. The converter prints the gap report (view CWEs missing from api_map `cwe`): add those rows by meaning.
- Parse big XML with ElementTree (tag counts, View/Category/Has_Member); never read the file whole.

## Reading results
- Many result files (RAW-00221): count first, then grep/jq only the rows needed; `uniq -c | head -n 20` for summaries.
- Same path/line/CWE from two tools counts once (ext_match groups; report marks "same as <tool> row").
- bandit severity under-rates real SQLi: rank by CWE, not tool severity.
- Labelled-out rows (vendored, minified, test, `logger_leak` CWE-532) stay in `b_out.jsonl`.
- `b_only` on a repo with no AI scan (manifest status init) is not an AI miss.

## Editing gotchas
- `sed 's#...#...#'` breaks when the text holds `#` (YAML/ini comments): use Edit or a python replace.
- A kit file change needs a line in `external/ext-scan/IMPORT.md` "Local changes".
- Kit prompts (conclude2, variant_*) are paid steps: only with the user's go and a per-run cap; adapt them
  into `ext/prompts/` (the frozen engine prompts are different files).
