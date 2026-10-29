# Phase 3 - Example checker
Task: TASK-003 · REQ-0002 · EPIC-002 · Status: draft (designer Nova, 2026-10-29)

## Goal
`python3 -I tools/examples/check_examples.py` validates every few-shot and eval pair against `examples/FORMAT.md`
and exits 0, or exits 1 with one `ERROR: <relpath>: <check>: <msg>` line per defect. `score_eval.py` scores
solver answers against `evals/keys/` without printing the key values. `examples/README.md` explains both.
It works when the unit tests pass ($0) and the real repo run exits 0 with the untouched english pair.

## Constraints
- Python 3.8 stdlib (no `removeprefix`, no `list[str]` at runtime), run as `python3 -I`. `-I` drops the script
  dir from `sys.path`, so every CLI inserts `os.path.dirname(os.path.abspath(__file__))` before `import exam_parse`.
- `examples/english/input-001.md` and `expected-001.md` never change (architecture.md:53).
- Keys: the checker reads keys only to compare; `score_eval` never prints key values and never writes prompts.
- No caching, so there is no cache-key risk. No network.

## Known incidents
none

## Design
### 3.1 Layout (owner: README + checker discovery)
`examples/<subject>/{input,expected}-NNN.md` (few-shot), `evals/inputs/<subject>/input-NNN.md`,
`evals/keys/<subject>/expected-NNN.md`, `tools/examples/{exam_parse,check_examples,score_eval}.py`,
`tools/examples/tests/test_*.py`. `<subject>` is one of `math|physics|english|literature`. A missing `evals/` tree
counts as an empty set. No empty dirs or `.gitkeep`: content tasks create the subject dirs. Item id = (subject, NNN).
Numbering is shared per subject: few-shot 001-002, eval 003-005 (Q2).

### 3.2 Shared parser `tools/examples/exam_parse.py` (the phase-2 name; phase 2 adds `validate_exam`)
- `read_text(path) -> str`: UTF-8, NFC.
- `header_fields(text) -> dict`: `Key: value` lines before the first `## `. `#` comments are stripped.
- `sections(text, level) -> list[(title, body)]`: splits on `#`*level headings.
- `parse_exam(path) -> dict`: `{fields, instructions, passage, questions:[{id, text, options:{A..D}}]}`.
  This is the phase-2 shape. Options are lines matching `^([A-D])\.\s+\S`.
- `parse_expected(path, legacy=False) -> {questions:[{id, final, correct, blocks:{name: body}}]}`. legacy=True
  also accepts a bare line equal to `Solution|Explanation|Verification|Grading|Question N` as a heading,
  `*` bullets and a trailing `.` on values.
- `norm(s) -> str`: NFC, casefold, collapsed whitespace, stripped trailing `.`. It is used for all comparisons.

### 3.3 `check_examples.py` (owner: `run_checks(root) -> list[str]`, `main(argv) -> int`)
CLI `[--root DIR]` (default: repo root from `__file__`). Exit 0 prints `OK: <n> pairs (<f> few-shot, <e> eval)`.
Exit 1 prints the ERROR lines. Exit 2 means a usage error or a missing root. Checks, each with an id in the message:
| id | Rule |
|---|---|
| pairing | each `input-NNN` has an `expected-NNN` (eval: in `evals/keys/<same subject>`) and vice versa. Unknown subject dir or stray file is an error |
| header | `Subject Level Exam type Task Mode` present. Subject matches the dir. Task/Mode in the FORMAT.md:22-26 enums. `Language` in vi/en if present (Q5) |
| sections | input has `## Instructions` and >= 1 `## Question N` (1..n, no gap). Mode Grade needs `## Learner answer`. Expected has the same question ids. Each expected question has `Final answer:`, `### Solution`, `### Explanation`, `### Verification`, `### Grading` |
| options | Task Multiple Choice, or any option line present: exactly A,B,C,D once each, in order. Expected `Final answer` is in A-D |
| verification | `### Verification` holds >= 1 `- Check:`, `- Final answer:` equal (norm) to the top one, and `- Status: Verified` |
| literature | Subject Literature: `Final answer: Open (rubric)`, `### Accepted interpretations` with >= 2 quotes, `### Model answer outline`. Every `"..."`/`“...”` quote in interpretations is a norm-substring of the input `## Passage` |
| disjoint-id | no (subject, NNN) appears in both few-shot and eval |
| disjoint-text | the norm(question text + options) of every question is unique across all inputs |
| input-key | no input (few-shot or eval) has `# Expected Output`, a heading named Solution/Explanation/Verification/Grading/Accepted interpretations/Model answer outline, or a line `[-*]? (Final answer|Correct answer|Status):` |
| key-leak | for each eval key, the lines of Solution/Explanation/Accepted interpretations, with quoted spans removed and length >= 40 after norm, must not occur in any eval input or any few-shot file |
Legacy allowance (Q1): `LEGACY = {"examples/english/expected-001.md": "<sha256>"}`. When the path and hash match,
the file is parsed with legacy=True. `Correct answer:` letter is the final answer, and only `- Check:`,
`### Grading` and the top `Final answer:` are waived. A `NOTE: legacy allowance: <path>` line is printed. A
changed hash means a full check.

### 3.4 `score_eval.py` (owner: `match(answer, key) -> bool|None`, `score_file(ans, key) -> list[(id, result)]`)
CLI `--answers-dir D [--keys-dir evals/keys]`. For each key `<subject>/expected-NNN.md`, the answer is read from
`D/<subject>/answer-NNN.md` (FORMAT expected layout; only `## Question N` + `Final answer:` are needed, Q4).
It refuses (exit 2) when D is inside the keys dir or the reverse. Output: `<subject>/NNN Q<n>: correct|wrong|missing|manual`
and `TOTAL <c>/<objective>`, with no key values. Exit 0 after scoring. `match`: `Open (rubric)` gives None (manual).
A letter A-D matches case-insensitively. An order `a-b-c` matches after spaces are removed. `<number> <unit>` matches
when the unit is equal (spaces removed) and |a-k| <= 0.5*10^-d (d = key decimals, `,` read as `.`). Anything else
uses an exact norm match. Phase 2 imports `match`.

### 3.5 `examples/README.md` (<= 80 lines)
It covers the layout table, a link to FORMAT.md, how to add an item, the check command, few-shot use, and the eval run
(main only: one fresh call per eval input file, empty temp cwd, no tools, never `evals/keys`; answers go to
`work/eval-runs/<ts>/<subject>/answer-NNN.md`, then `score_eval.py`). It links the skills `verify`, `crosscheck`
and `docs/design/phase-2-exam-pipeline.md` and does not copy them.

## Failure modes
| Failure | Response | Operator sees |
|---|---|---|
| missing pair file | exit 1 | `ERROR: examples/math/input-002.md: pairing: no expected-002.md` |
| key text in an eval input | exit 1 | `ERROR: evals/inputs/math/input-003.md: input-key: line 14 "Final answer:"` |
| legacy file edited | full check, likely exit 1 | normal ERROR lines, no NOTE |
| answers dir in the keys tree | exit 2 | `ERROR: answers dir overlaps keys dir` |

## Unit tests (`tools/examples/tests/test_check_examples.py`, `test_score_eval.py`, `test_exam_parse.py`)
Each test builds a temp root (`tempfile.TemporaryDirectory`) from a valid mini fixture (one MC english pair, one
literature pair, one eval math pair), injects one defect and asserts exit 1 plus the check id and file in the output.
| # | Test | AC |
|---|---|---|
| 1 | valid fixture -> 0, `OK:` | AC1 |
| 2 | remove expected / remove input -> 1, names the file | AC1 |
| 3 | eval input without key / key without input -> 1 | AC1 |
| 4 | same (subject, NNN) in few-shot and eval -> 1 disjoint-id | AC2 |
| 5 | eval question text equal after whitespace/case change -> 1 disjoint-text | AC2 |
| 6 | eval input gets `### Solution`, `Final answer: A`, `Correct answer:` (subTest each) -> 1 input-key | AC3 |
| 7 | eval key Solution line copied into a few-shot expected -> 1 key-leak; a quoted passage line alone -> 0 | AC3 |
| 8 | header field missing / bad enum / Subject vs dir -> 1 header | AC1 |
| 9 | 3 options, or E. option -> 1 options | AC1 |
| 10 | no `- Check:` / Status Unverified / Final answer mismatch -> 1 verification | AC1 |
| 11 | literature quote not in Passage -> 1; curly quotes -> 0 | AC1 |
| 12 | real repo english pair copied in with LEGACY path+hash -> 0 + NOTE; one byte changed -> 1 | AC1 |
| 13 | `match`: letter, order, `2.5 m/s^2` vs `2.50 m/s^2`, `2.6`, wrong unit, `Open (rubric)` -> None | AC4 |
| 14 | score_eval dir run: output has no key line text (sentinel in key Solution), missing answer -> `missing`, overlap -> 2 | AC4 |
| 15 | subprocess `python3 -I check_examples.py --root <tmp>` exits 0 (import path under -I) | AC5 |

## Verification
| Item | Command -> expected | Tier |
|---|---|---|
| 3.1-3.4 unit | `python3 -I -m unittest discover -s tools/examples/tests` -> OK | $0 |
| 3.3 repo | `python3 -I tools/examples/check_examples.py` -> exit 0, NOTE for expected-001 | $0 |
| 3.4 stdlib | `grep -hE '^(import|from) ' tools/examples/*.py` -> stdlib + exam_parse only | $0 |
| 3.5 | `wc -l examples/README.md` <= 80; links to the skills present | $0 |

## Decisions (proposed)
- Shared parser `exam_parse.py` (the phase-2 name) instead of readers inside the `check_examples` CLI, so the pipeline imports a module and not a script.
- Legacy allowance pinned by path and hash, not a lenient parser for everyone: FORMAT stays strict for new items.
- Leak check uses lines of 40 or more chars with quotes removed, not substrings: it avoids false hits on short answers ("A") and passage quotes.

## TASK steps
1. coder: `exam_parse.py`, `check_examples.py` (3.2, 3.3), `score_eval.py` (3.4), README (3.5). Compute the sha256 for LEGACY.
2. tester: tests 1-15, then the commands under Verification. 3. verifier: real repo run + AC1-AC5 evidence.

## Open questions (recommended answer first)
- [x] Q1 expected-001 handling: legacy allowance pinned by path+sha256 (recommended) / by path only / fail it.
- [x] Q2 ids: shared numbering per subject, eval starting at 003 (recommended, AC2) / numbering per tree (breaks AC2).
- [x] Q3 parser home: new `exam_parse.py` now (recommended) / readers inside check_examples.py (phase-2 table wording).
- [x] Q4 solver answer file: FORMAT expected layout Markdown (recommended) / result.json (phase 2, not built yet).
- [x] Q5 `Skill`/`Language` headers: optional (recommended; input-001 lacks them) / required (input-001 fails).

Answers: Q1-Q5 accepted as recommended (user, RAW-00030, 2026-10-29).

## Out of scope
Authoring the 20 items (content tasks). Detecting reworded duplicates. The phase-2 pipeline. Running a solver.
