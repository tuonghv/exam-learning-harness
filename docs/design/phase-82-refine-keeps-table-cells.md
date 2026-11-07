# TASK-082 design draft (REQ-0088) - refine keeps table cells
Suggested doc: docs/design/phase-82-refine-keeps-table-cells.md

## Goal
A data table the refine model only describes ("Table of bus fares ... 5x5 matrix") reaches the solver with its cell values,
so printed Math 64-67 (pdf p8) get answers, not declines.

## Root cause (evidence)
- prompts/dev/ingest/refine.md:8 rule 5: "tables you cannot transcribe: describe the kind briefly under `figures`" -> the
  model chose a kind-only description for the bus table (merged.json q64 figures); other figures on other pages kept values
  (bar/pie chart, the p? "Bảng 2 hàng ... 6,75; 7,38") -> model-dependent, not deterministic.
- The cells ARE in the native doc: plans/dhqg2024-t81/doc.json:4070 page 8 block b257 `type: table`, `rows`, text
  "Địa điểm | I | ... 10.000đ ..." (built by src/exam_engine/ingest/adapters/pdf.py:564-567,627-630 via find_tables).
- refine.py never reads native table blocks: `_page_text` (refine.py:248) is used only for similarity; the refined q
  figures come from the reply only (refine.py:508, 563). doc has no native `questions` here (by_id empty, refine.py:420),
  so any fix must work per page, not per original question.
- Propagation exists: api.py:116-127 (76.4) copies the carrier's figures to group members; api.py:210,218 render them as
  "[Figure/table: ...]" -> a figure entry added to q64 reaches 65-67 with no further change.

## Generality
Any exam whose PDF has native table blocks (pdf.py find_tables) or a docx `table` block (docx.py:195); no exam, subject or
language literal (matching is on the table's own cells). Docs without table blocks: output byte-identical.

## Design
### 82.1 Refine prompt transcribes tables and chart values (owner: prompts/dev/ingest/refine.md:8)
- Replace rule 5 with: "Tables: transcribe every cell under `figures`, one row per line, cells separated by ` | `
  (header row first). Charts and graphs: give the title, axis labels and every printed value/label. Only a picture with no
  printed values is described briefly." Keep rules 1-4, 6-12 verbatim (test_assembly_qa.py:197 asserts "\n12. Never ...").
- Cache: ReplyCache key = model + sha256(prompt) + image shas (refine.py:286) -> old replies are not reused; 
  `refined.prompt_sha256` (refine.py:602) changes as intended. No eval key, no answer content in the prompt.
### 82.2 Native-table fallback (owner: new `_native_tables(doc, qs)` in refine.py, called once just before refine.py:601)
- Input: `doc["pages"][*]["blocks"]` with `type == "table"` and non-empty `text` (only blocks the source extracted, i.e.
  `origin != "ai"`); `qs` the refined questions (dicts built at refine.py:561-571 / updated at 507-510).
- Pages of a question: `{q["page"]} | set(q.get("continued_pages") or ())`.
- `_cells(tb)`: non-empty stripped cells from `tb["rows"]` (else split `text` on "\n" and " | "); `data` = cells holding a
  digit, `labels` = the rest.
- Covered: a table is covered when >= 0.8 of its `data` cells (all cells if no `data`) occur in `fold()` of the joined
  text + context + options + figures of the questions on its page (reuse utils.text.fold). Covered tables: no change
  (keeps p? "Thời gian / P (atm)" table and every faithfully transcribed table untouched).
- Owner of an uncovered table: among figure entries of questions on that page, the one with the highest share of `labels`
  found as whole folded tokens (regex `\b<label>\b` on the folded entry); need share > 0; tie -> first in page order.
  None -> no change, append warning `{"code": "native_table_unplaced", "page": n, "message": ...}` to out["warnings"]
  (p1 structure table "Nội dung | Số câu" stays out: no figure entry matches its labels).
- Action: append one entry to the owner's `figures`: the table text exactly as `tb["text"]` (rows "\n", cells " | ").
  Keep the model's description (it says what the table is). Each table at most once per run.
- Returns the warning list; no change to `similarity`, `needs_review`, `validate_refined`, the schema (figures stays a list
  of strings: schema.py, refine.py:204,238) or the refined field list (test_refine_window.py:388).
- Window/recursive paths: the call sits before `out["refined"]` (refine.py:601); the recursive refine (613) runs its own pass.
### 82.3 Unit tests (owner: tests/unit/test_ingest_refine.py, new class NativeTable)
See Unit tests.
### 82.4 Real re-run of printed 64-67 (main runs it, cap $0.30)
See Verification.

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| Table on a page with no matching figure entry | no change | warning native_table_unplaced (page n) |
| Two tables, two figure entries | each table to its best-label entry | both figures carry cells |
| find_tables mis-split cells | text appended as extracted | solver may still decline; review pack |
| Model now transcribes cells (82.1) | table covered -> no duplicate | nothing new |

## Unit tests (mock only, no paid call)
- t1 bus fixture: synthetic doc page 8 with table block (rows copied from doc.json:4081.., 6x6) + mock reply q64 with the
  kind-only figure from merged.json -> q64 figures[-1] == table text; contains "10.000đ".
- t2 covered: same doc, reply figure already holds the cells -> figures unchanged, no warning.
- t3 two figures (bar chart labels "Đầu tư..." and table entry "Địa điểm I-V") on one page -> table goes to the "Địa điểm" one.
- t4 unplaced: table "Nội dung | Số câu" + reply with no figures -> no change, warning code native_table_unplaced.
- t5 golden: doc without table blocks -> refine output byte-identical to before (json.dumps of out["refined"] vs fixture).
- t6 synthetic non-DGNL exam (English labels "Year | Sales", page 2) -> appended (generality rule).
- t7 prompt: refine.md contains "every cell" and still "\n12. Never transcribe running headers".
- Suite: `python3 -I -m unittest discover -s tests/unit` -> no new failure.

## Verification
| Item | Command -> expected | Cost |
|---|---|---|
| 82.1 | grep -n "every cell" prompts/dev/ingest/refine.md -> rule 5 line | 0 |
| 82.2 | unittest NativeTable t1-t6 -> OK | 0 |
| 82.3 | full unit suite -> no new failure | 0 |
| 82.4 | main: re-refine p8 only of input/dgnl/De-thi-mau-DHQG-HCM-2024.pdf (1 call, ~$0.08, `--max-cost` 0.15), assemble Math, solve printed 64-67 only (`scripts/exam.py solve ... --real --max-cost-usd 0.15`, as plans/dhqg2024-t81/run-all.sh:6, restricted to 64-67) -> 4 answers, 0 declines, total <= $0.30 in cost.tsv | <=$0.30 |
Main must pick the exact id-filter flag from `scripts/exam.py solve --help` (not checked here; no Bash).

## Decisions
- Both 82.1 and 82.2: prompt alone is model-dependent and not mock-provable (AC1); fallback alone keeps a weak prompt.
- Append, not replace, the description: keeps model wording and similarity unaffected.
- Rejected: dump the whole native page text into context (noise, duplicates passages); rejected: k-th table -> k-th figure
  order pairing (a chart before the table would take it).

## Out of scope
OCR pages without native table blocks (only 82.1 helps there); docx flow unchanged except it benefits from 82.2 if refined.

## Defects
- D1 (major) prompts/dev/ingest/refine.md:8 rule 5 lets the model replace a transcribable table by a kind-only description;
  evidence plans/dhqg2024-t81/merged.json q64 figures vs doc.json:4071 table text.
- D2 (minor) refine.py ignores native `table` blocks of the refined page (refine.py:248-252 only for similarity; 508,563
  reply-only figures).

Nova

## Plan modes
No impact on single-source or pipeline plans: only the ingest refine step and its prompt change, the solve and plan code paths are untouched.
