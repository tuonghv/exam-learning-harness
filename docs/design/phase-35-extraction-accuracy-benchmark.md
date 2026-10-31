# Phase 35: extraction accuracy benchmark (TASK-035; REQ-0025)
# Phase 35 - extraction accuracy benchmark (draft for docs/design/phase-35-extraction-accuracy-benchmark.md)
Task: TASK-035 · REQ-0025 tier 0 (AC1 synthetic part, AC2-AC5) · Status: draft (Nova, designer)
## Goal
`python3 -I scripts/exam.py extract-eval GOLD.json EXTRACTED.json [--out DIR]` prints exact question-level
accuracy overall + per field (text, formula, options, figures), verified precision, needs_review rate, each
with k/n and Wilson 95% interval, plus a computed "99.999% needs ~300000 samples, not claimed" line. $0, no LLM.
## Constraints
- Stdlib only; read-only on inputs; never imports adapters/claude. Solver engine untouched.
- Exact = NFC + whitespace collapse/strip only. NEVER `utils/text.fold` (strips diacritics, text.py:5), `norm`
  (casefolds, text.py:29) or `refine.similarity` (difflib, refine.py:181): diacritic/case/sign errors must count.
- Gold holds question content only, no answers: reject `refine.FORBIDDEN` keys (refine.py:22) at load.
- No cached query body/rule changed -> no cache-key concern.
## Premise / reuse
- `ingest.schema.VERIFY_STATUSES` (schema.py:12), question `verification.status` (schema.py:39), `latex.text`
  (:29), `figures[].page` (:35). Doc questions: `{n, text, options:[{key,text}]}` (segment.py:18); refined
  questions: `{id, text, options:{A..}, figures:[]}` (refine.py:142). `refine.norm_id` (refine.py:111) for ids.
- Report pattern: `benchmark.summarize/report_md/write` (benchmark.py:77/95/130): summary dict -> md + json.
- CLI: add `"extract-eval"` to `COMMANDS` (cli.py:20) and `table` (cli.py:726); `extract_eval_main(argv)`
  in the style of `benchmark_main` (cli.py:532, argparse, exit 2 on usage).
## Design
### 35.1 loader `load_questions(path) -> {id: q}` (extract_eval.py)
Accepts a canonical doc or `{"questions":[...]}`. Per question -> canonical record:
`{"id": norm_id(q.get("id", q.get("n"))), "text": str, "formula": latex.text or q.get("formula") or "",
"options": {KEY: text} (list form [{key,text}] -> dict), "figures": sorted [page of each figure] (count+page;
asset ids/bbox ignored: they change per run), "status": verification.status or "unverified"}`.
Errors -> `ValueError` (CLI exit 2): unreadable/invalid JSON, no questions, id None, duplicate id,
FORBIDDEN key at top or question level, status not in VERIFY_STATUSES.
### 35.2 exact match `exact(a, b)` / `canon(s)`
`canon(s) = " ".join(unicodedata.normalize("NFC", s).split())`; case, diacritics, signs, `^`, braces kept.
Options equal iff same key set and canon equal per key. Figures equal iff lists equal. Question exact iff
all 4 fields equal. A gold id missing from extracted = all fields wrong; extracted ids not in gold = `extra`
(listed, not in the denominator).
### 35.3 metrics `evaluate(gold, extracted) -> summary dict`
`{"n": len(gold), "matched", "missing":[ids], "extra":[ids], "overall": R, "fields": {"text": R, "formula": R,
"options": R, "figures": R}, "applicable": {"formula": R, "figures": R}, "verified_precision": R,
"needs_review": R, "status_counts": {..}, "claims": {...}, "questions": [{id, status, wrong:[fields]}]}`,
`R = {"k", "n", "rate": k/n or None, "wilson": [lo, hi] or None}`. Field rates over all n gold; `applicable`
= only gold questions that have a formula / figure (so a mostly-empty field cannot look perfect).
Verified precision: k = exact among status "verified", n = number verified; n=0 -> rate/wilson None,
printed "n/a (0 verified)". needs_review: count status "needs_review" / n gold.
### 35.4 `wilson(k, n, z=1.959963984540054) -> (lo, hi) | None`
p=k/n; d=1+z²/n; c=(p+z²/2n)/d; h=z·sqrt(p(1-p)/n+z²/4n²)/d; (max(0,c-h), min(1,c+h)); n=0 -> None.
Known values (4 dp): (20,20)->(0.8389,1.0); (0,20)->(0.0,0.1611); (10,20)->(0.2993,0.7007); (8,10)->(0.4902,0.9433).
### 35.5 claims `zero_error_n(target, conf=0.95) = ceil(log(1-conf)/log(target))`
Computed, never hardcoded: 0.99->299, 0.999->2995, 0.99999->299572 (rule of three 3/ε ≈ 300000).
`claims = {"targets": {t: n_needed} for t in (0.99, 0.999, 0.99999), "supported_lower": overall.wilson[0]}`.
Report line: "99.999% is NOT claimed: needs >= 299572 error-free questions (n=20); 95% lower bound 83.89%."
### 35.6 report `report_md(sm)`, `write(sm, out_dir)` -> `extract_eval.json` + `extract_eval.md`
md: header (gold path, extracted path, n, matched/missing/extra), metrics table (Metric | k/n | rate |
Wilson 95%), Claims section (35.5 table "target | n needed"), "Wrong questions" list (id, fields, status).
Stdout = same metric lines (one per metric, `k/n = rate% (Wilson lo%-hi%)`) + claim line.
### 35.7 CLI `extract_eval_main(argv)` (cli.py) + thin wrapper reuse of scripts/exam.py
Args: `gold`, `extracted`, `--out DIR` (optional). Exit 0 = report produced (any accuracy; no gate);
2 = usage/input error (`ERROR: extract-eval: <msg>` on stderr). No --real/--mock: no LLM path exists.
### 35.8 gold + extracted fixtures
- Gold: `evals/extract/gold/synthetic-001.json` (`{"gold_version":"1","origin":"synthetic","questions":[..]}`),
  >=20 questions: >=5 Vietnamese diacritics, >=8 with latex (fractions, radicals, exponents, negative signs),
  >=15 with options A-D, >=3 with figures, >=2 table-in-text, >=2 open (no options). No answer/solution keys.
  Outside `evals/inputs`, `evals/keys`, `examples/` (scanned by examples_check.py:192-194, benchmark.discover).
- Extracted (tests/unit/fixtures/extract_eval/): `perfect.json` (gold in canonical doc question shape: `n`,
  options list, `latex{text,origin}`, `figures[{asset,page}]`, all `verified`) -> 20/20 everywhere;
  `corrupted.json` with fixed mutations: Q3 sign `-`->`+` (formula), Q5 `x^2`->`x^3` (formula), Q7 "Tính"->"Tinh"
  (text), Q9 B/C swapped (options), Q12 figure dropped, Q15 missing, extra Q99; all present ones `verified`
  -> overall 14/20, text 18/20, formula 17/20, options 18/20, figures 18/20, verified precision 14/19;
  `review.json`: perfect content, 4 `needs_review`, 1 `rejected`, 15 `verified` -> needs_review 4/20,
  precision 15/15; `none_verified.json`: all `unverified` -> precision n/a.
## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| bad JSON / missing file / dup id / FORBIDDEN key / bad status | ValueError -> exit 2 | `ERROR: extract-eval: ...` |
| 0 verified | precision None | `n/a (0 verified)` |
| extracted empty | all missing, rate 0/n | missing list in report |
## Unit tests (tests first: tests/unit/test_extract_eval.py)
1. wilson known values (35.4) to 4 dp, n=0 -> None, bounds clamp to [0,1].
2. zero_error_n: 0.99->299, 0.999->2995, 0.99999->299572; report text contains "299572" and "NOT claimed".
3. canon: NFC vs NFD "Tính" equal; "Tinh" != "Tính"; "x^2" != "x^3"; "-1" != "+1"; "A" != "a"; extra spaces equal.
4. perfect -> every rate 1.0, missing [], extra [].
5. corrupted -> exact k values of 35.8 (metric bites, AC4); assert perfect overall > corrupted overall.
6. review -> needs_review 4/20, precision 15/15; none_verified -> precision rate None, md says "n/a".
7. loader: list vs dict options and `n` vs `id` give equal records; dup id, FORBIDDEN `answer`, bad status,
   no questions -> ValueError.
8. gold guard: gold file has >=20 questions, category minimums of 35.8, no FORBIDDEN keys, path not under
   evals/inputs|keys|examples; `benchmark.discover("evals/inputs","evals/keys")` returns no gold path.
9. CLI: `main(["extract-eval", gold, perfect, "--out", tmp])` exit 0, both files written; missing file -> 2.
Anti-trivial: test 5 must assert the exact counts, not just "< 1.0"; test 8 counts categories in the file.
## Verification (tier 0, $0)
| Item | command -> expected |
|---|---|
| 35.1-35.6 | `python3 -I -m unittest discover -s tests/unit` -> all pass |
| 35.7 perfect | `python3 -I scripts/exam.py extract-eval evals/extract/gold/synthetic-001.json tests/unit/fixtures/extract_eval/perfect.json --out work/TASK-035/ev` -> exit 0, "overall 20/20", "NOT claimed", "299572" |
| 35.7 bite | same with corrupted.json -> "overall 14/20", "verified precision 14/19" |
| 35.7 error | gold vs nonexistent path -> exit 2, `ERROR: extract-eval:` |
| 35.8 leak | `python3 -I scripts/exam.py check-examples` -> unchanged PASS |
## Decisions (proposed)
- Exact = NFC+whitespace only - rejected fold/difflib - quality first, diacritics/signs are the errors we measure.
- Figures compared by page multiset - rejected asset id/bbox - unstable across runs, not fidelity.
- Wilson for intervals, exact zero-failure binomial for "n needed" - rejected Wilson-only - matches AC3 "~300000".
- No accuracy gate/exit 1 - REQ-0024 owns gating.
## Risks
- Gold leakage into solver inputs: separate dir + test 8; FORBIDDEN keys rejected at load.
- Trivial pass: perfect fixture derived from gold by hand-written shape change (not copied by code at test time).
- AC1 says "from synthetic PDFs": tier 0 gold is synthetic JSON with no rendered PDF; rendering it and running
  ingest end-to-end is a later tier. Main to confirm AC1 is only partially ticked by TASK-035.
## Out of scope
Real PDFs/user-labelled exams, paid vision/refine runs, PDF rendering of the gold, REQ-0024 verification gate.
## Defects
None found.
