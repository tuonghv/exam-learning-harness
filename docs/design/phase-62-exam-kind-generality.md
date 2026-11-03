# Phase 62 - Exam-kind generality (TASK-062)
Task: TASK-062, REQ-0068, RAW-00187 · Status: designed.

## Goal
- The engine parses, checks and generates a non-DGNL exam (other subjects, numbering, layout, language) by editing data only
  (`config/*.json`, prompt files), never code. Proof: synthetic non-DGNL fixtures pass in unit tests.
- Golden rule: with the shipped default config every old input gives byte-identical output (parse JSON, verify checks,
  cross canon, gen-exams files). Proof: golden tests (62.G) + full existing unit suite green.

## Constraints
- Python 3.8 stdlib. Config words are untrusted data: always `re.escape`d, never raw regex fragments.
- `Language:` header = explanation language (router.py:56-64), NOT the exam's language. So pattern tables are a
  union of enabled languages, not switched per exam (see Decisions D-1).
- Default prompt channel is `release v1.0.0` (config/engine.json:1); dev prompt edits do not change default runs.

## Plan modes
- Slice A (free, ship first): 62.1-62.6, 62.9. Deterministic, unit-tested, default config = byte-identical.
- Slice B (paid check by main): 62.7, 62.8. Change model-facing prompt bytes; need one A/B real run before any release bump.

## Design
### 62.G Golden harness (owner: new tests/unit/test_generality_golden.py) - do FIRST, before any edit
- Freeze, from the current code: every regex `.pattern` touched below (segment `_Q`, `GROUP_RE`, `_INTRO`, `_PART`,
  `_PART_ANY`; refine `PART_RE`; pdf `_PAGE_NO`; verifier `_VERDICT`; refcheck `_PAR_VI/_PAR_EN/_FIG/_NEEDS_TEXT`), the
  `cross._TF` dict, and sha256 of `genexam.build_prompt/input_md/key_md` for each of the 4 profiles with one fixed obj.
- Assert default config reproduces all of them exactly.

### 62.1 Language word table for ingest (owner: ingest/segment.py:4-27, ingest/refine.py:170, ingest/adapters/pdf.py:205)
- New data file `config/lang.json`; default `{"extra": {}}` (vi+en stay the built-in literals = today's table).
- Shape: `{"extra": {"<code>": {"question": [..], "group": [..], "range": [..], "intro": [..], "part": [..],
  "page": [..], "true": [..], "false": [..], "paragraph": [..], "figure": [..], "needs_text": [..],
  "scripts": [..]}}}` - every key optional, values are plain words.
- New helper `exam_engine/utils/langtable.py`: `load(config_dir=None) -> dict` (missing file -> `{"extra": {}}`;
  malformed -> ValueError naming the file), `words(slot, table) -> [escaped words of all extra langs, sorted]`,
  `alt(base, slot, table) -> base if no words else "(?:" + base + "|" + "|".join(words) + ")"`.
- segment.py: wrap each word group via `alt()`: `_Q` start words (Câu|Cau|Question), GROUP_RE/_INTRO lead words and
  range words (`-|–|đến|to`), `_PART`/`_PART_ANY` (`PH[ẦA]N|PART`), refine.PART_RE uses the same `part` slot.
  Expose `segment.build(table) -> namespace of compiled regexes`; module globals = `build(langtable.load())`
  so tests call `build()` with a synthetic table instead of reloading modules.
- pdf.py:205 `_PAGE_NO`: `(?:Trang|Page)` -> `alt(..., "page")`; `/|of` stays; `- N -` is the language-free fallback.
- Fallback for an unknown language: numeric starts already exist (`(\d+)[.)]` in `_Q`, `MARK` at segment.py:29).
- Generic signal: question-start word + number at line start; part word + Roman/Arabic numeral.
- Test (synthetic, built in the test, no exam text): table `{"fr": {"question": ["Exercice"], "part": ["PARTIE"],
  "range": ["à"], "page": ["Seite"]}}`; 6 questions numbered `Exercice 1`, `Q2.`, `3)`; headings `PARTIE A`/`PARTIE 2`
  restart numbering; footer `Seite 2 von 4` dropped (`von` is NOT in the table -> assert kept; documents limit);
  group `Exercice 3 à 5` spans (3,5). Also an English-only exam with `Question 1`/`PART II` parses as today.

### 62.2 True/false verdict table (owner: pipeline/verifier.py:35, pipeline/cross.py:16,98)
- `verifier._VERDICT` = `alt` over `true`+`false` slots appended after today's alternatives; `cross._TF` = today's dict
  updated with `{w.casefold(): "T"}` / `"F"` from the extra words. cross.py:98 lookups use `.casefold()` (today
  `.lower()`; identical for vi/en words - golden asserts).
- Test: extra `{"de": {"true": ["richtig"], "false": ["falsch"]}}`; answer `a) richtig b) falsch c) richtig d) falsch`
  -> 4 verdicts, canon `V:TFTF`; default table gives today's result on `a) Đ b) S c) T d) F`.

### 62.3 Reference checks (owner: core/refcheck.py:10-17,23,157-159)
- `_refs` iterates `(_PAR_VI, _PAR_EN) + extra` where extra = one compiled paragraph regex from `paragraph` words, same
  group layout `(\()(\d)\)|(\d)`. `_FIG` and `_NEEDS_TEXT` get one appended `|\b(?:words)\b` alternative each.
- Test: extra `{"fr": {"paragraph": ["paragraphe"], "figure": ["figure ci-dessous"]}}` -> `paragraphe (3)` missing
  marker reported as `paragraph (3)`; default table returns today's list on the existing refcheck tests.

### 62.4 Answer shapes and open tasks from subject config (owner: pipeline/verifier.py:38-57, pipeline/reporter.py:43-44,
  pipeline/examples_check.py:161)
- `config/subjects.json`: optional `"answer_shapes": ["tf4", "number"]` added to math and physics only; optional
  `"label"`. `DEFAULT_POLICY` (router.py) gets `answer_shapes: []`.
- verifier `_part_format`: gate `key in ("math","physics")` -> `"tf4"`/`"number"` in `policy["answer_shapes"]`
  (each shape checked separately). Open-fail detail: `"%s answer must be Open" % (policy.get("label") or "Literature")`
  -> identical bytes for today's config.
- reporter `_is_open`: keep both old conditions, add `or router.policy(exam subject)["task"] == "Open"` (risk R3).
- examples_check:161 `sub == "literature"` -> `router.policy(sub)["task"] == "Open"`; error kind string stays
  `"literature"` (check output unchanged). LEGACY (line 22) stays: it is repo data, one hash.
- Test: temp `EXAM_ENGINE_CONFIG_DIR` with subject `chemistry` (`answer_shapes:["number"]`) and `history`
  (`task: Open`, `label: History`): a chemistry numeric item checks `answer holds a number`; a history non-Open answer
  fails with `History answer must be Open`; math/physics/literature unchanged.

### 62.5 Allowed scripts for garble test (owner: ingest/adapters/pdf.py:275-286)
- `_odd_chars`: `name.startswith("LATIN")` -> any of `("LATIN",) + scripts` from the table (`scripts` slot, e.g.
  `"GREEK"`, `"CYRILLIC"`).
- Test: Cyrillic token is odd with default table, not odd with `{"ru": {"scripts": ["CYRILLIC"]}}`.

### 62.6 gen-exams profiles as data (owner: pipeline/genexam.py:16-41,222-262, cli.py:939-955)
- New `config/genexam_profiles.json`: `{"<name>": {"subject", "prompt", "qa_prompt", "topics": [..], "check":
  "reply|mc4|mc", "blind": bool, "exam_type", "level", "lang", "instructions", "grading_line", "subject_label"}}`
  holding today's 4 profiles verbatim (strings moved, not reworded). `check` names map to the existing functions
  (`check_reply`, `check_dgnl`, `check_mc`) in a small code dict; unknown name -> GenError `bad_profile`.
- `PROFILES`, `BLIND`, `PROFILE_SUBJECT`, `PROMPT_OF`, `TOPICS`, `SUBJECTS`, `LANG_MC`, `CHECKS` become views of the
  loaded file (names kept so tests/cli keep working). `input_md`/`key_md` keep their 3 branch shapes (incl. the blank-line
  quirk, Defect D3); only literals come from the profile. `cli --profile` choices/default from the file
  (default = first key `hs`). Prompt files stay where they are (no move; Decisions D-4).
- Test: a synthetic profile `{"bio-mc": subject "biology", lang "en", topics ["cells"], check "mc"}` in a temp config
  -> `build_prompt` names topic `cells`, `input_md` header `Subject: Biology`, `Language: en`; golden for the 4 old ones.

### 62.7 Part structure in the image prompt (owner: pipeline/cross.py:17-23,44-48) - slice B
- `IMAGE_RULES`: drop the literal `(Part I 1-12, Part II 1-4, ...)` and `Part II and III included`; insert
  `%s` = `structure_hint(text)`: from the route-A text, headings matched by `segment._PART_ANY` / `_is_heading_line`
  and the printed numbers after each (`segment._Q`) -> `"Printed numbering restarts per part: <heading> 1-12; <heading> 1-4."`;
  no heading or no restart -> `"Printed numbering may restart per part or section."`. "Answer every question in every part."
- `route_b_prompt(exam, text=None)`; caller passes the text it already has (no new input).
- Test: synthetic text with `SECTION 1` (Q1-3) and `SECTION 2` (Q1-2) -> hint lists both spans; no headings -> generic line.

### 62.8 Generic dev prompt wording (owner: prompts/dev/system.md:1-2, lang/vi/system.md:1-2,
  verification/verify_answer.md:1-2, exam/solve.md:11, lang/vi/exam/solve.md:11, genexam_qa.md:1) - slice B
- Replace "Vietnamese Grade 12 ... (Mathematics, Physics, English, Literature)" by "expert solver of school and
  university-entrance exam questions; the exam header names subject, level and language". The header already reaches
  the model (solver.py:64). solve.md:11 "Literature or other open task" -> "an open (essay/rubric) task".
- genexam.md / genexam_dgnl*.md stay: each is one profile's own prompt. genexam_qa.md: per-profile `qa_prompt` (62.6)
  so a new profile can point at its own reviewer text; hs keeps the current file.
- Dev channel only, no release bump. Cache: refine cache key = model + prompt text + image sha (refine.py:282), so changed
  prompt text never reuses old replies; solve has no reply cache.

### 62.9 Generality line in the design template (owner: main; files main owns)
- Where: `.claude/skills/design/SKILL.md` §Design doc structure, a line under `## Constraints`; mirror one bullet in
  `docs/guide/architecture.md` §Invariants.
- Draft: `Generality: no exam-, subject- or language-specific literal in code; a new exam kind is data
  (config/subjects.json, config/lang.json, config/genexam_profiles.json, prompts); default config keeps old inputs
  byte-identical (golden test named); one test uses a synthetic non-DGNL exam (other subject, numbering, layout, language).`

## Unit tests
- test_generality_golden.py (62.G): frozen patterns/dict/shas equal under default config.
- test_langtable.py: load missing/empty/malformed file; `alt` returns base unchanged when no words; words are escaped
  (`"a.b"` matches only literally, `"(x"` does not raise).
- Per item the synthetic test named in 62.1-62.7 (fixtures built in code; no exam text, no keys).
- Existing suite unchanged and green: `python3 -I -m unittest discover -s tests/unit`.

## Verification
| Item | command -> expected | tier |
|---|---|---|
| 62.G, 62.1-62.6 | `python3 -I -m unittest discover -s tests/unit` -> OK, new tests listed | free |
| golden on real data | main: parse/check every `examples/*/input-*.md` before and after the change, diff the JSON -> empty | free |
| 62.6 | gen-exams `--dry-run` per old profile (cli.py:939-965), sha of printed prompt before/after -> equal | free |
| 62.7 | one cross-solve on one existing exam, route B only, compare answers to the last run -> no new disagreement | paid, main |
| 62.8 | one solve on the dev channel of one existing exam vs release run -> same answers | paid, main |
| 62.9 | grep `Generality:` in the two files -> 1 hit each | free |

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| config/lang.json missing | built-in vi+en only | nothing (today's behaviour) |
| lang.json malformed / wrong type | ValueError at import naming the file | CLI exits with the file name |
| extra word collides with content (e.g. `Q` as question word) | more lines read as question starts | synthetic test per word; doc note: use whole words only |
| short verdict word (`v`) matches prose | false 4-verdict canon | test asserts free-text answers do not reach 4 verdicts |
| profile file lacks a key / unknown check | GenError `bad_profile` before any call | error line, exit 1, cost 0 |
| reporter Open widening (R3) | literature-like subjects now shown open | golden reporter tests; only Open-task subjects affected |

## Decisions
- D-1 Union of enabled languages, not switched by `Language:` - switching rejected: `Language:` is the explanation
  language and DGNL pages mix vi and en; segmentation runs before any language is known.
- D-2 vi+en stay as code literals, data only adds languages - full data-driven vi/en rejected: pattern drift risk,
  byte-identical proof would need string reconstruction; no user gain.
- D-3 Words not regex in config - raw fragments rejected: untrusted clone, ReDoS/injection.
- D-4 genexam prompt files not moved to prompts/dev/profiles/ - churn only; the config row points at the file.
- D-5 cross structure derived from route-A text headings - counts from config rejected (exam-specific again).
- D-6 utils/text.py detect_lang stays vi/en ("en" is a safe explanation fallback for `auto`).

- D-7 (coordinator) Defects D1 (genexam manifest records the hs prompt hash for every profile) and D2 (`PART` accepted as a part heading in segment.py:22 and refine.py:170) are fixed inside TASK-062: both are generality bugs and cheap.
- D-8 (coordinator) Order: 62.G first, then slice A (62.1-62.6, 62.9, D1, D2, free); slice B (62.7 route-B prompt, 62.8 dev prompts) needs a paid check run by the coordinator inside caps (RAW-00186).
## Out of scope
- Release prompt bump; renaming dgnl-named tests/evals; gold_pdf furniture (test helper); refine.py:29 cost comment;
  detect_lang for more scripts; options beyond A-D (segment `_OPT`, verifier:59) - separate REQ if wanted.

## Defects
- D1 medium genexam.py:342: manifest `prompt_sha256` hashes the hs template (`template()` default) for every profile;
  dgnl/dgnl-en/dgnl-vi runs record the wrong prompt hash. Fix: hash `template(PROMPT_OF[profile])` (changes manifest
  bytes for non-hs profiles; main decides whether inside TASK-062).
- D2 low segment.py:22 / refine.py:170: `_PART`/`PART_RE` accept only `PHẦN`, while `_PART_ANY` (segment.py:27) also
  accepts `PART`; an English `PART I` heading is not stripped from a context. Fix changes bytes for English exams: separate item.
- D3 low genexam.py:233 vs 226: the no-passage MC branch writes one extra blank line before the options; kept for golden.
- D4 info audit generality.md:9,11: cross.py:16 and verifier.py:35 are vi+en, not Vietnamese-only; gap is "no third language".
- D5 low pdf.py:281: Greek letters other than `π` count as odd chars, so math pages using α/β may get garble flags;
  62.5 lets config add `GREEK`, default unchanged.

Nova
