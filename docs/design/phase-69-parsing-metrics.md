# Phase 69 - Parsing accuracy apart from solving (draft for docs/design/phase-69-parse-accuracy-metrics.md)
Task: TASK-069 · REQ-0074 (RAW-00192, brief tmp/Exam-Structure-Context.md §7) · Supersedes: phase-65 §65.9 (its sketch) · Status: draft
Note: guard refused work/TASK-069/handoff/design.md (role bound to TASK-068); written here instead.

## Goal
Parsing errors are measured and printed on their own, so an extraction failure is never read as a solver
failure. Seen when: `metrics.structure_scores` gives the hand-computed rates (69.1 tests); the gold set
(69.2) scores 1.0 except the named known misses; the board prints a `parsing` line apart from the `quality`
line and splits wrong answers into parse-suspect vs solver (69.4); input tokens per question printed (69.6).

## Constraints
- Pure, $0, stdlib, no new AI call. scorer.py (TASK-068) not touched.
- Old outputs byte-identical: `compute()` without `structure=` -> metrics.json unchanged; board text unchanged
  when no `input/assembly.json`, no `--structure-gold` and no run.log prompt bytes.
- Gold holds synthetic text only (from tests/unit/test_structure_{scope,qa}.py), never real exam text, never answer keys.
- No prompt, refine or reply-cache input changes -> no cache key concern.

## Generality
Any exam kind parsed by parser.parse_exam (section path, instruction, passage, stem, pages); no exam/subject literal;
gold cases are synthetic non-DGNL (English-shaped and lettered/Roman headings, restarts).

## Known incidents
none.

## Plan modes
Solve/retry/QA: unaffected (read-only metrics). Board: new lines only when sources exist. Cross-solve: unaffected.

## Design
### 69.1 `structure_scores(exam, gold)` (owner: pipeline/metrics.py, new pure function)
- In: `exam` = parse_exam dict; `gold` = list of gold rows (69.2). Out:
  `{"n_gold", "n_exam", "extra": [ids], "scores": {metric: {"k","n","rate","miss":[{"id","why"}]}},
  "tokens_per_question_est": float|None}`; rate = k/n, None when n == 0 (metrics `_rate`).
- Match by exam position id (int). Field metrics count only gold rows that carry the field AND were extracted
  (a missing question is counted once, in extraction). Text compare = `extract_eval.squash` (reuse).
| metric | n | correct when | miss why |
|---|---|---|---|
| extraction | len(gold) + len(extra) | gold id present in exam | missing / extra |
| boundary | rows with `stem` | squash(q.stem) == squash(gold.stem) (whole stem: foreign or dropped text fails) | cut |
| hierarchy | rows with `section` | q.section == gold.section (` > ` path, strip) | section |
| instruction | rows with `instruction` | squash(effective) == squash(gold); effective = join(non-empty [section_notes.get(section) (65.4, absent today), q.instruction]) | missing (gold set, exam empty) / leak (else) |
| shared_ref | rows with `shared` | {gold ids p: p.section==q.section and squash(parser._passage(p)) == squash(parser._passage(q)) != ""} ∪ {q} == {gold ids with same `shared` label} | unlinked / overlinked |
| reference | rows with `deps` | sorted(parser.deps(exam).get(id, [])) == gold.deps | wrong_target |
| cross_page | rows with len(pages) > 1 | q.pages == gold.pages and boundary ok | pages / cut |
- tokens_per_question_est = round(B / 4 / n_exam, 1); B = UTF-8 bytes of, per `parser.groups(exam)` group,
  instruction + passage once (55.4 render rule) + every stem + option texts. `BYTES_PER_TOKEN = 4` named
  constant (rough for Latin text, under-counts Vietnamese; a relative measure between parses, not a bill).
- `parser._passage` reused (same function groups() uses, so shared_ref matches what render sees); not copied.

### 69.2 Gold fixture (owner: tests/unit/fixtures/structure_gold.json, new)
- One file: `{"schema": "structure-gold/1", "cases": [{"case": "<TestClass.test_name>", "refined": [<synthetic q
  dicts as fed to api._from_refined, copied from the test>], "gold": [{"id": 1, "stem": "...", "section": "...",
  "instruction": "...", "shared": "g1", "deps": [], "pages": [1, 2]}], "known_miss": {"<metric>": [ids]}}]}`;
  every gold field except `id` optional.
- Cases: the structure cases of test_structure_scope.py (20) and test_structure_qa.py (16) whose input is a refined
  list (option-bank-only cases gold only `id`/`stem`). Test inputs stay inline in those tests (not edited).
- `known_miss`: P3 (unranged section instruction, needs 65.4) and P7 (reference after restart, needs 65.7) if still
  failing at implementation time; coder records what the run gives, tester checks each miss maps to gap G5/G6.

### 69.3 compute(structure=) (owner: metrics.compute, _quality)
- `structure` = {id str: [codes]} (from assembly rows). Given (even `{}`): rows get `parse_flag` (bool),
  `counts["structure_flags"] = {code: n}`, `by_parse_flag = {"flagged": _slice, "clean": _slice}`. None: no key.
- `_quality` (board only), keys only when given: `parse_flagged` (n flagged), `parse_wrong` (key-wrong answered
  and flagged), `solve_wrong` (= wrong_answered - parse_wrong); qa basis: `parse_differs` (QA differs, flagged).
  Name differs from the existing engine-review `flagged` on purpose.

### 69.4 Board parsing line (owner: cli._rs_board_load cli.py:1394, metrics._side :568, metrics.board_text :622)
- `_rs_board_load`: read `<run dir>/input/assembly.json` (planrun.py:236 copies it; schema assembly/1, cli.py:543) if
  present -> `{row["id"]: row.get("structure", [])}` -> `compute(..., structure=)`; absent/unreadable -> None.
- `_side`: sum the 69.3 keys with `_sum` (None when no run has them).
- `board_text`, after the quality lines, only when `parse_flagged` is not None:
  `  parsing flagged P/N (structure flags, not accuracy)  wrong: parse-suspect X solver Y` (qa basis: `differs on flagged X`).
  The `quality`/`score` lines are untouched: solving accuracy keeps its denominator; parsing never enters it.

### 69.5 Board gold scores (owner: cli board parser cli.py:1500 `--structure-gold FILE`, needs `--exam`)
- Loads a gold list (69.2 `gold` shape) for the one shown exam, `structure_scores(parse_exam(a.exam), gold)`, prints
  per kind block: `  parsing gold n=G extraction 75.0% boundary 100.0% hierarchy ... cross_page -` (`-` = n 0);
  `--json` adds `"structure_gold"`. No flag -> no line. A real-exam gold is hand-made by the user with id/section/
  shared/deps/pages only (no text fields), so no exam text is stored (D-1).

### 69.6 Input tokens per question (owner: metrics._side, board_text)
- `_side` adds `in_tok_per_q = sum(prompt_kb) * 1024 / BYTES_PER_TOKEN / n` (all LLM calls in run.log: solve, retry,
  QA), None when any run has no log. Own line `  input ~tok/q N (prompt bytes/4, all calls)` only when not None;
  cost line text unchanged. Static estimate for a parse = 69.1 `tokens_per_question_est`.

### 69.7 When 65.4 / 65.7 become justified (record under Decisions; no code)
- 65.4 (section note): instruction `missing` on >= 1 question of a NON-synthetic gold (69.5), or >= 1 key-wrong
  answer whose reviewed cause is "section instruction not in prompt". Synthetic P3 miss alone = mechanism shown,
  not loss (by construction). Guard: the note must not raise tokens_per_question_est > 5% on the gold set.
- 65.7 (restart refs): reference `wrong_target` on a non-synthetic gold, or `group_link_uncertain` in
  exam_warnings of a real restarted exam with a key-wrong dependent question. Else stays deferred.
- 65 D (Claude structure read): parse_flagged / N > 5% on a real run (69.4 line), as phase 65 E.4 says.

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| gold id beyond exam | extraction miss `missing` | rate < 1, miss list |
| exam renumbered vs gold | matched by position, field metrics drop | hierarchy/boundary misses -> gold or parse shift |
| assembly.json absent (markdown exam) | structure=None | no parsing line (old board) |
| assembly ids != result ids (`--questions` selection) | ids not in result ignored | parse_flagged counts matched ids only |
| gold bad JSON / no `--exam` | ValueError -> exit 2 | `ERROR: --structure-gold ...` |
| run.log missing | in_tok_per_q None | no input line |
| non-Latin text | token estimate low | label says `~`, bytes/4 |

## Unit tests (tests/unit/test_structure_scores.py, tier 0)
- T1 hand-computed: exam (dict, text = stem) q1 {sec A, ins "Read and answer.", passage "P", stem "Pick one."},
  q2 same with "Pick two.", q3 {sec B, ins "Read and answer.", passage "", stem "Pick three.", pages [2,3]};
  gold 1-2 {stem, section A, instruction "Read and answer.", shared g1}, 3 {stem, section B, instruction "",
  pages [2,3], deps []}, 4 {stem "Pick four.", section B}. Expect extraction 3/4 = 0.75 (miss 4 missing),
  boundary 3/3, hierarchy 3/3, instruction 2/3 (miss 3 leak), shared_ref 2/2, reference 1/1, cross_page 1/1,
  tokens_per_question_est = round(62/4/3, 1) = 5.2 (groups (16+1) + 16 bytes, stems 9+9+11).
- T2 extra: exam adds q5 not in gold -> extraction 3/5, extra [5]. T3 field absent everywhere -> metric n 0, rate None.
- T4 shared_ref overlinked: q3 given section A + passage "P" -> exam set {1,2,3} vs gold {1,2} -> shared_ref 0/2.
- T5 gold set: every case of structure_gold.json through api._from_refined + parse_exam (emit helper) -> each
  metric 1.0 except `known_miss` ids, which must miss (a fixed gap fails the test -> update the fixture, by design).
- T6 compute(structure=None) == compute() on the mock result (json.dumps equal); compute(structure={"2":
  ["range_overrun"]}) -> by_parse_flag flagged n 1, counts.structure_flags {range_overrun: 1}.
- T7 _quality with key: q2 flagged and wrong, q3 unflagged wrong -> parse_wrong 1, solve_wrong 1.
- T8 board_text: block with parse keys prints the parsing line; block without -> lines equal to today's.
- T9 in_tok_per_q: prompt_kb 2.0, n 4 -> 2048/4/4 = 128.0; a run without log -> None, no line.
- T10 gold file has no answer-key fields (`answer`, `key`); every `refined` text occurs in a test source file.

## Verification
| Item | command -> expected | tier |
|---|---|---|
| 69.1, 69.3, 69.6 | `python3 -I -m unittest tests.unit.test_structure_scores -v` -> OK | 0 |
| 69.2 | same, T5 -> per-case scores; known misses listed | 0 |
| no regress | `python3 -I -m unittest discover -s tests/unit` -> OK | 0 |
| 69.4 | `run-stats board` on a saved run dir with input/assembly.json -> parsing line; one without -> output equal to before (diff) | 0 |
| 69.5 | `run-stats board --exam E --structure-gold G` on a synthetic exam with a saved run -> parsing gold line | 0 |

## Decisions
- One fixture file with cases (rejected: 35 files; moving test inputs out of tests = churn).
- Position-id match (rejected: text alignment, needs exam text and is extract_eval's job, REQ-0025).
- Real runs get flags, not accuracy: without gold there is no parsing accuracy; the line says so.
- Reuse extract_eval.squash and parser._passage/groups/deps; no new parser logic.
- D-1 (main, pick ONE): (a) 69.5 board `--structure-gold` flag (recommended: AC1 "board prints parsing accuracy";
  ~15 lines) (b) gold scores only in unit tests, board shows flags only.

- D-coordinator-1 (answers D-1) option (a): a board `--structure-gold FILE` flag; the gold lives next to synthetic fixtures, real runs without gold show parse flags and split wrong answers into parse-suspect vs solver.
- D-coordinator-2 phase-65 line 91 wording fix (KB, not tokens) and the duplicate AC1 line in REQ-0074 are cleaned in this task.
## Out of scope
65.4/65.7 themselves; a DGNL/real-exam gold (user-made); refine/AI structure reading; extract_eval text metrics.

## Defects
- R1 minor docs/req/items/REQ-0074.md:26 empty duplicate `- [ ] AC1:` line (ledger; main's file).
- R2 minor docs/design/phase-65-exam-structure-scope.md:91 "Avg input tokens/question = _log_cost bytes / n" yields
  KB, not tokens; 69.6 defines bytes/4 (superseded here, DONE doc not edited).
- R3 guard: designer role bound to TASK-068, refused work/TASK-069/handoff/design.md; main to rebind or copy.

Nova
