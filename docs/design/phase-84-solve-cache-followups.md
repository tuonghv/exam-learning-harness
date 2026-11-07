PROGRESS: COMPLETE
SKILLS: design, token-efficiency
# Phase 84 - Solve cache follow-ups
Task: TASK-084 · REQ-0090 · Supersedes: phase-83-solve-cache §83.4, §83.1 (hit check), Out of scope (DEF-1)

## Goal
- "already solved" shows the original paid run; build_result tolerates a runner without `cache`; bad cached cost is a miss;
  refine/boundary reply caches key on a pinned model ID; metrics cache line has a real test.

## Design
### 84.1 AC1 paid run in last_solved (owner: planrun.last_solved, src/exam_engine/pipeline/planrun.py:182-188)
- Paid run = `calls > 0` or `cached` absent/0. Selection key: `(paid, finished_utc)`, max wins
  -> newest paid run; if no paid run, newest done run (old behaviour). Return dict shape unchanged.
- cli.py:104 message unchanged (it already prints `prev[cost_usd]`, `prev[calls]`, `prev[dir]`).
### 84.2 AC2 guard (owner: engine.build_result, engine.py:429)
- `rn.cache is not None` -> `getattr(rn, "cache", None) is not None`; `rn.hits`/`rn.saved` read only inside that branch.
### 84.3 AC3 cost range (owner: Runner._hit, engine.py:56-57)
- Valid hit adds: `math.isfinite(float(cost_usd)) and cost_usd >= 0` (keep bool exclusion). Else miss -> real call,
  entry rewritten by the existing put (engine.py:94). `import math` if absent.
### 84.4 AC4 pinned model in ingest caches (owner: new `claude.resolve(model, pins) -> str` in adapters/claude.py next to `pinned` :22)
- `resolve` = `pins.get(model, model)`. Call sites, `--real` only (mock/dry-run untouched, goldens byte-identical):
  - refine_main cli.py:749-758: `a.model = claude.resolve(a.model, pins)`; then `claude.pinned(a.model, pins)`; not ok ->
    stderr `ERROR: model '<m>' is an alias; the refine cache needs a pinned ID: <hint>`, return 2 before mkdtemp/any call.
    Resolved ID then feeds both make_real_llm (call) and refine(..., model) -> key refine.py:329 and `refined.model`.
  - ingest boundary cli.py:552-558: `m = claude.resolve("haiku", pins)` when `args.real`, pass `m` to make_real_ask and
    Reviewer (key boundary.py:301). "haiku" is in model_pins, so no refusal path is reachable here; still assert pinned.
  - `pins = settings.load_config("engine").get("model_pins")` (same source as cli.py:97).
- refine.py / boundary.py code unchanged: the key format stays, only the model string fed in is pinned.
- Chosen: resolve through model_pins, refuse only what stays unpinned (unknown alias, `-latest`). Rejected: refuse every
  alias - breaks default `ingest refine --real` (default "sonnet", cli.py:698) and boundary (hard-coded "haiku").
### 84.5 AC5 metrics line (owner: tests only; metrics.block metrics.py:499, line 531)
- Replace the vacuous assert at tests/unit/test_solve_cache.py:220 (hasattr fallback) with a direct test (below).

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| only cached reruns exist (paid run dir deleted) | newest done run shown | cost=$0.0 calls=0 (as today) |
| cached cost NaN/-1/"x" | miss, paid call, entry rewritten | normal cost |
| refine --real --model foo-latest / unknown alias | exit 2, no call, no tmp dir | ERROR naming hint |
| existing refine/boundary entries keyed "sonnet"/"haiku" | one-time miss after upgrade | one paid re-call per page/window |
| model_pins entry wrong ID | claude call fails as today | claude error |

## Unit tests (tests/unit, stdlib, tmp dirs)
1. 84.1: tmp plans/<id>/ with run A (calls=5, cost 0.12, older) + run B (calls=0, cached=5, newer) -> last_solved returns A;
   only B -> B; A without `cached` key (pre-83 run) counts as paid.
2. 84.2: build_result with a stub runner lacking `cache` -> no raise, `run` has no `cached`/`cost_saved_usd`.
3. 84.3: subTests cost_usd in (-1, float("nan"), float("inf"), "0.1", True, None) -> llm called once; 0 and 0.05 -> hit.
   NaN written via a raw file (json allows NaN).
4. 84.4: `claude.resolve` table (sonnet -> pin, claude-x-1 -> same, unknown -> same); refine_main --real --model sonnet
   (llm patched) -> cache key / make_real_llm got model_pins["sonnet"]; --model foo-latest -> exit 2, 0 calls;
   --mock run unchanged (refined.model == "sonnet"); boundary Reviewer built with pinned haiku when --real.
5. 84.5: `metrics.block({... cost: {cached: 3, cost_saved_usd: 0.1234}})` contains exactly `cache: hits=3 saved=$0.1234`;
   cached None -> no `cache:` line.

## Verification
| Item | command -> expected | tier |
|---|---|---|
| 84.1-84.5 | `python3 -I -m unittest discover -s tests/unit` -> OK | free |
| 84.1 real | main: re-run phase-83 proof dir (paid + cached --yes run exist) without --yes -> line shows paid run cost/calls | free |

## Plan modes
- No impact on single-source or pipeline plans: 84.1 reads plan.json only; 84.2/84.3 sit in Runner/build_result used by both
  identically; 84.4 is ingest-only (before any plan exists).

## Decisions (user, RAW-00251, 2026-11-07)
- D1 AC4 = (a): resolve aliases through model_pins, refuse only unresolved; one-time re-call of pages/windows cached under "sonnet"/"haiku" keys. Chosen as the best option (keeps default ingest --real working, no stale alias hits).

## Out of scope
- Other `--real` commands with alias models and no cache (cross, benchmark, genexam: cli.py:848/961/1047).

## Defects
- DEF-84-1 (low) tests/unit/test_solve_cache.py:220: `... if hasattr(metrics, "block") else "cache: hits="` makes the
  assert vacuous when `block` is missing; fixed by 84.5.
- DEF-84-2 (info) cli.py:554/558 hard-code "haiku" for boundary instead of a config value; kept, only resolved via pins.

Nova
