# Phase 11: Informatics subject + bilingual subject names (REQ-0015, TASK-011; EPIC-004)

## Goal
Resolve Vietnamese and English subject names (diacritics optional) to one canonical key; add `informatics` with 5 checkable examples. Scope accepted (RAW-00046): THPT level, checkable answers only (number systems, boolean logic, algorithm trace, SQL result, data size / network arithmetic); no free-form programming essays.

## Code (config-driven; reuse router and examples_check)
- `utils/text.py`: `fold(s)` = NFD, drop combining marks, `đ`->`d`, casefold, collapse spaces.
- `pipeline/router.py`: `subject_key`, `known_names` compare with `fold`; `examples_check.py:73` uses `router.subject_key(header)` instead of the casefold dict.
- `config/subjects.json`: aliases add vi names: math `toán`, physics `vật lý`, literature `ngữ văn`, `văn`, english `tiếng anh`, new `informatics` (`tin học`, `it`, `information technology`, `informatics`, `cntt`) with `task: Closed`, `checks: [format, computed, quote]`, `score_basis: official_key`, `language: vi`, `prompt: subjects/informatics.md`.
- Prompts: `prompts/dev/subjects/informatics.md` (one rule line: state the representation/base/schema first, show the trace table, give the exact value) and `prompts/dev/lang/vi/subjects/informatics.md`. Contract needs no change (`*` subject, no markers). No release in this task (default stays v1.0.0; a later release picks it up).
- `examples/FORMAT.md`: subject list gains `informatics`; per-subject section for Informatics (Given/representation first, trace table or truth table in Solution, `Check:` recompute another way, edge cases: base prefix, overflow/carry, NULL/duplicate rows, off-by-one loop bound).

## Content (coder B): 5 original Vietnamese items in `examples/informatics/` (001-002, few-shot) and `evals/inputs|keys/informatics/` (003-005)
001 binary<->decimal MC; 002 boolean expression value MC; 003 loop trace (value after the loop, off-by-one trap); 004 SQL query result (small table in the question, count or value, NULL/duplicate trap); 005 data size or IP host count (calculation with unit and rounding, `expr` recomputable). One correct option per MC with a reason per distractor. Answers must be recomputable with Python stdlib (int/bin, boolean eval, loop simulation, sqlite3, arithmetic).

## Tests
Router: every alias (with and without diacritics, any case) resolves; unknown subject rejected; a header `Subject: Tin hoc` routes to `informatics` (parse + solver dry-run uses its overlay). Oracle: `tests/unit/test_examples_oracle.py` gains Informatics recomputes with Python only (never reading the key text to derive the answer). `check-examples` OK with the new subject; suite green.
