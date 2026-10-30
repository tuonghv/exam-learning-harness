# Phase 29: answer sheet + learning view (TASK-029; REQ-0034, REQ-0035)

## Premise
TASK-029 = REQ-0034 (answer sheet, default) + REQ-0035 phase 1 (learn view). Report stage only:
solver, schemas, result.json, engine logic unchanged. Decisions in brief are final (ids as stored,
zfill 2; null/Open/non A-D -> `—`; fenced monospace block at top + answers.md; `--view sheet|learn`).
Known incidents: none checked (main to grep docs/notes/incidents.md for "report"/"pdf").

## Plan modes
- report subcommand (cli.py:174): gets `--view`; the only switch.
- engine.run (engine.py:142): unchanged call -> default `view="sheet"`; runs get the sheet for free.
- --no-pdf: md + answers.md only; pdf path: md2html renders the fence as `<pre><code>`.

## Reuse
| Need | Reuse | Where |
|---|---|---|
| sanitize id/subject/model text | `_one_line` (ZWSP before leading ``` / # / -) | reporter.py:25 |
| Open detection | `_is_open(q, exam)` | reporter.py:39 |
| full report body | `build_markdown` unchanged | reporter.py:47 |
| fence -> `<pre><code>`, html-escaped | md2html.convert | md2html.py:175-186 |
| monospace font stack | `code {font-family: "DejaVu Sans Mono", ...}` | md2html.py:52 |
| PDF render | `md_to_pdf` (title = report.md line 1) | reporter.py:169,183 |

## Design
### 29.1 Answer sheet builder (owner: reporter.py, new, after `_num` :43)
- `CIRCLED = {"A": "Ⓐ", "B": "Ⓑ", "C": "Ⓒ", "D": "Ⓓ"}`; `DASH = "—"` (U+2014); header dash `–` (U+2013).
- `_sheet_id(qid) -> str`: `s = _one_line(qid)`; if `re.fullmatch(r"[0-9]+", s)` -> `s.zfill(2)`
  ("7"->"07", "31"->"31", "100"->"100", "007"->"007"); else `s` as is ("1a", "II.3"); empty -> "?".
- `_sheet_mark(q, exam) -> str`: `DASH` if `_is_open(q, exam)`; else `CIRCLED.get(str(answer).strip())`
  when answer is a str, else `DASH` (null, "a", "D.", "3.46", "AB" all -> `—`; no case folding = exact mapping).
- `build_answer_sheet(result) -> str`: returns exactly
  ```` ```text\n<Subject> – <N> Questions\n\n<rows>\n```\n ````
  Subject = `_one_line(exam.get("subject")) or "Exam"`, N = `len(result["questions"])`, order = stored order.
  Rows: chunks of 5; width `w = max(2, max(len(id)))` over all ids (one width for the whole sheet);
  cells `ljust(w)` joined by 3 spaces, trailing spaces stripped; number line then mark line; one blank
  line between row pairs. Last partial row = fewer cells, no padding cells. 0 questions -> header only.
  No verdict, cost, explanation or stats.
- Example (Science, real data has nulls at 7-9):
  ```text
  Science – 30 Questions

  01   02   03   04   05
  Ⓒ    Ⓑ    Ⓓ    Ⓒ    Ⓒ

  06   07   08   09   10
  Ⓐ    —    —    —    ...
  ```
  ids 31..35 -> `31   32   33   34   35`; ids 98..102 -> w=3: `098`? NO: zfill(2) only, so `98 ` `99 ` `100` `101` `102` (ljust 3).

### 29.2 Learning view builder (owner: reporter.py, new)
- `build_learning_view(result) -> str` (markdown, no fence):
  `## Learning view` then per question `### Question <_sheet_id>`, bullets:
  `- Answer: <mark> (<raw letter>)` for A-D; `- Answer: Open (needs a human rubric)` if open; `- Answer: —` otherwise;
  append ` — verdict <STATUS>` only when `verification_status != "PASS"` (honest: answer is the engine's, not a key).
  `- Why: <_one_line(explanation)>` if present; `- Steps:` + `1. ...` from `solution` (`_one_line` each) if present;
  `- Key concept: ...` / `- Common mistake: ...` only if `q.get("key_concept")` / `q.get("common_mistake")` truthy.
  Missing fields -> line omitted (never "none"). Formula/diagram refs kept because text passes through `_one_line` unchanged.

### 29.3 Composition + files (owner: `write_reports` reporter.py:228)
- Signature: `write_reports(result, out_dir, *, pdf=True, renderer=None, runner=subprocess.Popen, view="sheet")`.
- `VIEWS = ("sheet", "learn")`; unknown view -> `ValueError("unknown view %r" % view)` before writing.
- `_compose(result, view) -> str`: `body = build_markdown(result)`; `title, rest = body.split("\n", 1)`;
  return `title + "\n\n" + block + "\n" + rest.lstrip("\n")` where block = `"## Answer sheet\n\n" + build_answer_sheet(result)`
  (sheet) or `build_learning_view(result)` (learn). Title stays line 1 -> md_to_pdf title (:183) unchanged.
- `build_markdown` is NOT changed: test_2_model_fence (test_exam_report.py:205) asserts no `"\n```"` in
  its output, so the fenced sheet must be added in `write_reports`, not inside `build_markdown`.
- Always also write `answers.md` = `build_answer_sheet(result)`; return dict gains key `"answers"` (path).
- engine.py:142 unchanged.

### 29.4 CLI switch (owner: cli.py `report_main` :174)
- Usage: `exam.py report RESULT.json --out DIR [--no-pdf] [--view sheet|learn]`.
- Parse: pop `--view V` (or `--view=V`) from argv before the existing `len(args) != 3` check; missing
  value or V not in `reporter.VIEWS` -> usage line + rc 2. Pass `view=V` to `write_reports`.
- Print `report answers -> <path>` in the existing key loop (add "answers" to the tuple :186).

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| non-numeric / odd id | printed via `_one_line`, no zfill | id as stored |
| id or subject starts with ``` | ZWSP from `_one_line`; md2html fence check `startswith("```")` fails | literal text, fence intact |
| answer null / "Open" / "3.46" | `—` | dash |
| bad `--view` | rc 2, usage | usage on stderr |
| font lacks Ⓐ-Ⓓ in mono stack | browser fallback glyph, column drift | misaligned PDF (verify V4) |

## Unit tests (tests first; new class `AnswerSheet`/`LearnView` in tests/unit/test_exam_report.py, existing tests untouched)
1. ids "1".."10", answers A-D -> exact expected string (header, 2 rows, 3-space sep, circled letters).
2. null, "Open", "a", "D.", "3.46", "" -> `—`; literature task with "A" -> `—` (`_is_open`).
3. ids 31..60 -> first row `31   32   33   34   35`; no offset applied.
4. ids 98..102 -> width 3, `100` intact, all cells ljust(3); "7" -> "07", "007" kept.
5. non-numeric id "1a" and id "```x" -> printed, block still one `<pre>` in md2html.convert, no extra fence.
6. 7 questions -> last row has 2 cells, no trailing spaces; 0 questions -> header only.
7. sheet contains no "Verdict", "cost", "Explanation", "PASS".
8. write_reports(pdf=False): report.md line 1 starts "# Exam report:", "## Answer sheet" before "## Question 1";
   answers.md == build_answer_sheet(r); info["answers"] set; `build_markdown(r)` output byte-identical to before (no fence).
9. HTML: write_reports with fake renderer "junk" -> report.html has `<pre><code class="lang-text">` containing "Ⓓ" and "—".
10. view="learn": "## Learning view", "Why:", "Steps:", no "Key concept:" when absent; present when fields set; non-PASS shows verdict.
11. view="bogus" -> ValueError, no files written. CLI: `report_main([...,"--view","bogus"])` -> 2; `--view` w/o value -> 2.
12. Vietnamese subject "Tiếng Việt" header kept; html lang="vi".

## Verification (main runs; cost tier 0, no LLM)
| Item | command -> expected |
|---|---|
| V1 sheet md | `python3 -I exam.py report work/dgnl-real/run-Science/result.json --out work/TASK-029/v/sci --no-pdf` -> answers.md header "Science – 30 Questions", 6 row pairs, `—` count == number of null answers (`grep -c '"answer": null'`) |
| V2 4 subjects | same for Math, English, Vietnamese -> 4 answers.md, each 30 cells, ids 01..30 |
| V3 learn | `... --view learn --no-pdf` on Vietnamese -> "## Learning view", 30 "### Question", no "Key concept" |
| V4 PDF/font | `fc-list ':charset=24b6' family` lists a family in the md2html mono stack (DejaVu Sans Mono expected); then run without `--no-pdf` -> report.pdf ok, `pdftotext -layout report.pdf - \| head -n 12` shows aligned circled letters; else record misalignment as defect |
| V5 regression | `python3 -I -m unittest discover -s tests/unit` -> all pass |

## Risks
- Coordinator check (fc-list): DejaVu Sans Mono has NO U+24B6; only Noto (Sans) Mono CJK has it, where the glyph is typically double width. So V4 will likely show column drift; planned fix = add "Noto Sans Mono CJK SC" to the `code` font stack in md2html.py:52 (item 29.5, in scope) and pad cells by measured width. Original risk: circled letters may be absent from DejaVu Sans Mono or be East-Asian-ambiguous width -> column drift in PDF/terminal. Fallback (only if V4 fails, ask main): CSS `pre code` font add "DejaVu Sans" for those glyphs, or wider cell sep. Not designed now.
- "Correct answer" in learn view is the engine's answer, not a key; verdict suffix mitigates.
- report.md gets a new section above `## Question 1`; downstream parsers of report.md (none found) would see it.
- No cached query/rule touched -> no cache-key issue.

## Out of scope
Combined multi-subject sheet; PDF-original numbering offset (31..60); phase 2 key_concept/common_mistake
generation (schema+prompt); hiding verbose sections in learn view; `--view` on `run`.

## Defects
- D-DES-1 (low, brief/REQ-0034 Design): "build_answer_sheet ... called from build_markdown" conflicts with
  test_exam_report.py:205 (`"\n```"` must not appear in build_markdown output). Resolved here by composing in write_reports.
