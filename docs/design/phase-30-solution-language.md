# Phase 30: solution language (TASK-030; REQ-0036)
# Phase 30 - solution language (draft for main) · Task: TASK-030 · REQ-0036 AC1-AC4 · Nova
Suggested doc: `docs/design/phase-30-solution-language.md`. Builds on phase-29 §29.2 (`build_learning_view`).
## Goal
Explanations are vi for every subject (English included, unknown subject included) unless the run says
`--lang en|auto`; the learn view labels follow the solution language. Proof: tier-0 tests + learn view
of `work/dgnl-real/run-English/result.json` shows vi labels, no re-solve.
## Premise (facts checked)
- `router.language` (src/exam_engine/pipeline/router.py:39-43): header `Language:` > subject policy > "vi".
- Runtime solve prompt is `prompts/<rel>/exam/solve.md` (dev line 4/8: `Language: vi|en`); it does NOT know
  `auto`. `docs/prompts/exam/solver.md:16,31,45` is not loaded by solver.py (see Defect D1). So `auto` must be
  resolved to vi|en in code before the prompt. Solver prompt text unchanged.
- `settings.read_prompt(rel, lang)` (settings.py:69) picks `lang/vi/...` for vi: English exams now get
  `prompts/dev/lang/vi/subjects/english.md` + vi system.md (exists in dev, v1.1.0+; default release v1.0.0 has none).
- No LLM answer cache in solve (only sha256 of sources/prompts); no cache key to update.
- All 12 `work/dgnl-real/*/result.json` have `exam.language: "vi"` (line 10).
## Precedence (30.1)
| # | Source | Example | Result |
|---|---|---|---|
| 1 | CLI `--lang vi|en|auto` (solve) | `--lang en` on a `Language: vi` exam | en |
| 2 | exam header `Language:` | `Language: en`, no flag | en |
| 3 | subject policy `language` (config/subjects.json) | English, no header | vi (was en) |
| 4 | DEFAULT_POLICY / unknown subject | `Subject: Chemistry` | vi |
`auto` at any level -> `detect_lang(question texts)` -> vi|en. `result.exam.language` is then always vi|en.
## Design
### 30.1 Config + router (owner: config/subjects.json:10, router.py:39)
- subjects.json english `"language": "en"` -> `"vi"`. No other key changes.
- `router.language(exam, override=None) -> "vi"|"en"`: `lang = override or header or policy or "vi"`;
  `if lang == "auto": lang = text.detect_lang(" ".join(q.get("text","") for q in exam["questions"]))`.
  Other values returned as today (untrusted value stays guarded by settings.CODE_RE).
- `router.apply_lang(exam, lang) -> None`: if lang: `exam["fields"]["Language"] = lang` (so solver.py:18,52,77,
  engine.py:83, cross.py:41 all see it with no signature change).
### 30.2 CLI `--lang` (owner: cli.py:26 solve_main)
- `ap.add_argument("--lang", choices=("vi","en","auto"), help="explanation language (beats header Language:)")`.
- `cfg["lang"] = a.lang` (cli.py:65); dry-run path: `router.apply_lang(exam, a.lang)` after cli.py:74.
- engine.run (engine.py:104): `router.apply_lang(exam, cfg.get("lang"))` right after `parse_exam`.
### 30.3 Detector (owner: src/exam_engine/utils/text.py, new fn, stdlib)
- `detect_lang(s) -> "vi"|"en"`: NFC; words = alpha tokens; vi-word = contains a char of
  `ăâđêôơưĂÂĐÊÔƠƯ` or U+1EA0-U+1EF9 or a/e/i/o/u/y with acute/grave (àáèéìíòóùúỳý...); return "vi" if
  vi-words/words >= 0.15 else "en"; empty -> "vi" (the default). Ratio, not "any", so an English exam with a
  Vietnamese instruction line stays en ("dominant language").
### 30.4 Learn-view labels (owner: reporter.py:84 build_learning_view)
- `LABELS = {"en": {...}, "vi": {...}}` keys: title, question, answer, open, verdict, why, steps, key_concept,
  common_mistake. en = today's strings exactly ("Learning view", "Question", "Answer", "Open (needs a human
  rubric)", "verdict", "Why", "Steps", "Key concept", "Common mistake"). vi proposal: "Phần học", "Câu",
  "Đáp án", "Mở (cần chấm theo thang điểm)", "kết quả", "Vì sao", "Các bước", "Khái niệm chính",
  "Lỗi thường gặp". Status codes PASS/FAIL/UNCERTAIN stay raw.
- `learn_lang(result) -> "vi"|"en"`: `exam.language` if in LABELS, else `detect_lang` over all
  explanation+solution text (old/edited results, "auto", junk).
- Answer sheet (`build_answer_sheet`, reporter.py:71) and `build_markdown` unchanged (header stays English).
- reporter.py:319 `md_to_pdf(lang=...)`: use `learn_lang(result)` so `<html lang>` is never "auto".
## Failure modes
| Failure | Response | Operator sees |
|---|---|---|
| `--lang fr` | argparse error, exit 2 | usage line |
| header `Language: auto` | detector resolves | result.exam.language vi/en |
| result language missing/junk | detector on explanations | labels match text |
| English exam + vi prompt variant reads oddly | prompt unchanged; real run is AC4 paid step | review of real run |
## Unit tests (tier 0, write first)
1. test_router: English, no header -> "vi" (flip line 44 from "en"); Physics vi; unknown subject vi.
2. override beats header: `language({"fields":{"Subject":"Math","Language":"vi"},...}, "en") == "en"`;
   header beats policy (`Language: en` on Math -> en).
3. auto: English question texts -> en; Vietnamese texts -> vi; English with one vi instruction -> en.
4. `apply_lang(exam, None)` leaves fields untouched; `apply_lang(exam,"en")` sets Language.
5. cli: `solve x.md --dry-run --lang en` prompt contains `Language: en`; `--lang fr` exit 2; no flag on
   English example -> `Language: vi`.
6. engine mock run with cfg lang "en" -> result.exam.language "en".
7. reporter: result language "vi" -> "Đáp án:", "Vì sao:", "Các bước:", "Khái niệm chính:", "Lỗi thường gặp:";
   "en" -> existing test_10 strings unchanged; language "auto"/missing with vi explanation -> vi labels;
   answer sheet identical for vi and en (header "– N Questions").
8. detect_lang: "" -> vi; pure ASCII English -> en.
## Verification (written before implementation)
| Item | Command -> expected | Tier |
|---|---|---|
| 30.1-30.4 | `python3 -I -m unittest discover -s tests/unit` -> OK, 0 failures | 0 |
| 30.2 | `exam.py solve examples/<english>.md --dry-run` -> `Language: vi`; `--lang en` -> `Language: en` | 0 |
| 30.4 | `exam.py report work/dgnl-real/run-English/result.json --out work/TASK-030/rep-vi --no-pdf --view learn`; grep report.md -> `Đáp án:` present, `- Answer:` absent, sheet header unchanged | 0 |
| 30.4 en | same with a copy of that result where `exam.language="en"` -> English labels | 0 |
| AC4 real | `--real --lang en` on one subject only after user's go | paid (main) |
## Decisions (coordinator, user delegated "choose your best")
1. vi label wording as proposed. 2. Localize title/question/open too (consistency). 3. Keep `language` key per subject. 4. Docs fix D1/D2 in scope: examples/FORMAT.md:28 and a note in docs/prompts/exam/solver.md that `auto` is resolved in code.
## Risks
- Flipping english to vi switches English exams to `lang/vi` prompt variants (dev/v1.1.0+): behaviour change
  of prompts, intended by RAW-00125, seen only in a paid run.
- Generated English exams carry `Language: en` (genexam.py:40 LANG_MC) -> header beats vi default: they still
  explain in English. Intended by precedence row 2; flag to user if AC2 means "all English exams".
- Detector threshold 0.15 is heuristic; only used for `auto` and legacy results.
## Out of scope
Translating existing results, re-solving, solver/solve.md prompt rewrite, genexam header change,
FORMAT.md:28 wording ("default: the language of the exam" is now wrong; main updates docs).
## Defects
- D1 (low, docs) docs/prompts/exam/solver.md:16,31,45 claims `solution_language: auto` and "English
  questions -> English by default"; runtime prompts/*/exam/solve.md:4 only supports `Language: vi|en`, and
  solver.py:19 never loads solver.md. Evidence: grep `solver.md` in src -> none.
- D2 (low, docs) examples/FORMAT.md:28 "default: the language of the exam" contradicts REQ-0036 (vi default).
