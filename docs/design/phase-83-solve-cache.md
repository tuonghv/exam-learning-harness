PROGRESS: COMPLETE
SKILLS: design, token-efficiency

# Phase 83 - Solve cache 
Task: TASK-083 · REQ-0089 (AC1-AC8, Q1/Q2 answered) · Status: draft

## Goal
`exam solve --real` reuses a stored reply for any model call whose (pinned model ID, prompt, images) is unchanged:
0 calls, $0, identical result.json. Re-solving an exam already solved prints when/model/cost and asks first.
Proof: small exam (<= 5 questions) solved once, re-run -> `calls=0`, `cached=N`.

## Constraints
- Reuse `ReplyCache` (src/exam_engine/ingest/replycache.py:13) unchanged; no new cache module (AC6).
- Eval keys: `cfg["key"]` never enters the cache key or entry. Today it only reaches `solver.fewshot`
  (solver.py:42, used to EXCLUDE the key file) and `scorer.apply_key` (engine.py:472, after all calls) -> prompts are key-free.
- Mock/dry-run never touch the disk cache (`--mock` -> no cache object at all).
- Default (no `--real`) runs byte-identical: new result/plan/index fields appear only when a cache is active.
- Stdlib only; no shell changes.

## Generality
All exam kinds: the key is over the rendered prompt, no subject/language literal; synthetic non-DGNL exam in one test.

## Known incidents
none found (not grepped `docs/notes/incidents.md`; main to check).

## Design
### 83.1 Call-level cache in Runner (owner: engine.py:39 `Runner`)
- `Runner(cfg, llm, log, sink=None, llm_images=None, cache=None)`; `cache` = ReplyCache or None.
- One choke point: every solve/QA/retry/image/second-sample call goes through `Runner.call` (engine.py:47),
  so caching there covers all rounds; later prompts are built from earlier replies, so identical hits => identical run.
- `key = "%s\0%s\0%s" % (cfg["model"], sha256(prompt), ",".join(sha256(png) for png in images or ()))`
  - same shape as refine.py:329; namespace `"solve"`. Question/data content is inside the prompt
  (solver.solve_prompt renders the exam text; retry/QA prompts embed questions + prior answers).
- Order in `call`: cap checks stay first (a hit is free, but keep caps simple: check hits BEFORE the cap checks
  so a fully cached run never trips `call_cap`). Flow: if `cache` and not `fresh`: `hit = cache.get("solve", key)`;
  valid hit = dict with `text` non-empty str and `cost_usd` number, else miss (AC5 corrupt -> miss; ReplyCache
  already maps unreadable/invalid JSON to None, replycache.py:30).
- Hit: build `claude.Call(True, hit["text"], 0.0, "", "", 0.0)`; `self.hits += 1`; `self.saved += hit["cost_usd"]`;
  log line `cache hit seq=%d tag=%s saved=%.4f prompt_sha256=%s` (must NOT contain `dur=`/`prompt_bytes=`/`answer_bytes=`:
  metrics._LOG_RE metrics.py:18 sums those; must not match planrun._CALL_RE planrun.py:172); sink gets `cached=True`.
- Miss: existing path; after the call, if `c.ok`: `cache.put("solve", key, {"text": c.text, "cost_usd": c.cost_usd or 0.0,
  "model": cfg["model"], "tag": tag, "created_utc": <iso>})`. Failed calls are never stored.
- `fresh=True` (from `--fresh`): skip `get`, still `put` (refreshes entries).

### 83.2 Pinned model rule (owner: new `claude.pinned(model) -> (ok, hint)` in adapters/claude.py; check in cli.solve_main)
- Pinned iff starts with `claude-`, contains a digit, does not end with `-latest`, and is not a key of
  `config/engine.json` `model_pins`. Data only: `"model_pins": {"sonnet": "<full id>", "opus": "...", "haiku": "..."}`
  (full IDs filled by main/user, not guessed here).
- `--real` with an unpinned model -> exit 2, before any call/plan dir:
  `ERROR: model 'sonnet' is an alias; the solve cache needs a pinned ID: --model <model_pins[sonnet]>` (AC3).
  Unknown alias without a pin: same message with `--model claude-<family>-<version>`.
- Not applied to `--mock`/`--dry-run` (default config "sonnet" keeps goldens byte-identical).

### 83.3 Per-exam cache dir (owner: cli.solve_main, cli.py:157)
- `cache_dir = os.path.join(DEFAULT_OUT_ROOT, planrun.exam_id_of(a.exam), "cache")` -> `plans/<exam-id>/cache/`,
  i.e. beside that exam's own run dirs (AC8, Q2); same for `--out` runs (cache is per exam file, not per run dir).
- `cache = replycache.ReplyCache(cache_dir)` only with `--real`; mock -> `None`. Pass to `engine.run(..., cache=, fresh=)`
  -> `Runner`. No sharing: another exam has another `<exam-id>`.
- `plans/<exam-id>/cache` has no plan.json; `_already_imported` (planrun.py:176) already skips such dirs.

### 83.4 Already-solved check (owner: new `planrun.last_solved(root, exam_path) -> dict|None`; cli.solve_main before `claim_run_dir`, cli.py:94)
- Artifact = `plans/<exam-id>/*/plan.json` (PlanWriter, planrun.py:99) with `source=="solve"`, `status=="done"`,
  `llm=="claude-p"`, `exam.sha256 == metrics.file_sha256(a.exam)`; newest by `finished_utc`. Returns
  `{dir, finished_utc, model, cost_usd, calls}`.
- Only for `--real`. If found and not `--fresh`, print:
  `already solved: <finished_utc> model=<model> cost=$<cost_usd> calls=<n> -> <dir>`
  `re-run reads the cache (unchanged calls cost $0); --fresh forces a full paid re-solve`
  - TTY (`sys.stdin.isatty()`): prompt `re-run? [y/N] `; `y` -> continue with cache; else exit 0, no call.
  - no TTY: refuse, exit 2, hint names `--fresh` and `--yes` (Q1).
- `--fresh` (new flag, store_true): no check, no cache reads, writes still happen.
- `--yes` (new flag, see D2): non-interactive "confirmed": continue with cache reads.

### 83.5 Trace and metrics (owner: engine.build_result engine.py:391, planrun.record planrun.py:114, metrics.compute metrics.py:188)
- result.json `run`: only when a cache is active add `"cached": rn.hits, "cost_saved_usd": round(rn.saved, 6)`
  (add both as optional props in schemas/result.schema.json `run` if it is closed). `calls`/`cost_usd` count real calls only.
- calls/index.jsonl: hit rows get `"cached": true`, `cost_usd: 0.0`; file numbering uses a sequence `n = calls + hits`
  (Runner passes it), so prompts/replies of hits are still captured (trace marks `cached`, AC1). Miss rows unchanged.
- plan.json: `cached`, `cost_saved_usd` in `finish` when present in `run`.
- metrics `cost`: `cached=run.get("cached")`, `cost_saved_usd=run.get("cost_saved_usd")`; `metrics.block` prints
  `cache: hits=N saved=$X` only when not None (AC5). CLI summary line unchanged.

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| corrupt/partial cache file | miss, real call, entry rewritten | nothing (cost as normal) |
| cache dir unwritable | ReplyCache.put swallows OSError (replycache.py:43) | run ok, re-run misses |
| alias model with --real | exit 2 before any call | message naming the full ID |
| already solved, no TTY | exit 2, no plan dir, no call | when/model/cost + `--fresh`/`--yes` hint |
| prompt release/channel changed | prompt text differs -> miss | normal paid call |
| two exam files with the same stem | share `plans/<stem>/` (existing behaviour); hits only for byte-identical prompts | see D3 |

## Unit tests (tests/unit, stdlib, fake llm counting calls; tmp dirs)
1. AC1: engine.run twice with the same ReplyCache(tmp) -> 2nd run llm called 0 times, result.json questions identical, run.cached == 1st run calls, index rows `cached: true`.
2. AC2: change model / one prompt byte (subject addendum via tmp prompt) / one question's text -> llm called again (3 subtests).
3. AC3: `claude.pinned` table: sonnet, opus, haiku, claude-x-latest, "claude-sonnet" -> rejected; pinned IDs accepted; solve_main --real --model sonnet -> exit 2, stderr names model_pins value, no plans/ dir.
4. AC4: tmp plans/<id>/<run>/plan.json done+same sha -> solve_main --real (llm patched) with stdin non-TTY -> exit 2, 0 calls, stderr has when/model/cost; `--fresh` -> proceeds, cache not read; `--yes` -> proceeds, cache read; different exam sha -> no prompt.
5. AC5: write garbage + wrong-shape JSON into the entry file -> miss, 1 call; metrics.cost has cached/cost_saved_usd; block prints cache line.
6. AC8: two exams -> two `plans/<id>/cache` dirs; exam B run creates no file in A's dir.
7. Eval key: run with `--key` -> no cache entry or key string contains the key file content or path.
8. Mock: solve_main --mock never creates `plans/*/cache`; default mock run result.json/index.jsonl byte-identical to golden (no new fields).
9. Synthetic non-DGNL exam used in test 1.

## Verification
| Item | command -> expected | tier |
|---|---|---|
| 83.1-83.5 | `python3 -I -m unittest discover -s tests/unit` -> OK | free |
| AC7 proof run 1 | main: `exam solve <small exam, 3-5 q> --real --model <pinned> --max-cost-usd 0.30` -> calls>0, `plans/<id>/cache/solve-*.json` exist | paid, tiny |
| AC7 proof run 2 | same + `--yes` (no TTY) -> `calls=0`, `cache: hits=N saved=$X`, result.json questions identical (diff of run 1 vs 2 `questions`) | free |
| AC4 refuse | same without `--yes` -> exit 2, prints when/model/cost, no new plan dir | free |
Then scale to a full exam only after the user approves (RAW-00242).

## Decisions (user, RAW-00245 "accept all", 2026-11-07)
- D1 (a): alias rejected only for `--real`; config default stays "sonnet"; add `model_pins` alias -> full ID.
- D2: approved, new `--yes` flag (non-interactive confirm of a re-run on a solved exam).
- D3 (a): same-stem exam files share `plans/<exam-id>/` (existing identity).
- Reuse the ReplyCache key shape of refine.py:329 over a new store (AC6).

## Out of scope
- Pinning model aliases in ingest refine/boundary caches (see Defects).
- Cache eviction/size limits; cross-exam sharing (Q2 says never).

## Defects
- DEF-1 (low) src/exam_engine/ingest/refine.py:329 and boundary.py:301: reply-cache keys use the model as given (defaults "sonnet" cli.py:674/782, "haiku" boundary.py:288), an unpinned alias -> stale hits after an alias moves to a new snapshot. Same rule as 83.2 would fix; separate task.
- DEF-2 (info) config/engine.json default `"model": "sonnet"` is an alias; with 83.2 every default `--real` solve is refused until D1 is settled.

## Plan modes
Single-source and pipeline plans both solve through `Runner.call`, so both get the cache with no change to plan structure. The cache dir is per exam id (`plans/<exam-id>/cache/`); pipeline sub-plans of one exam share it, other exams never do. Mock runs never read the disk cache.
