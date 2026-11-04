# Phase 78: verified solve gate (TASK-078; REQ-0024)

Decisions (coordinator, user: pick your best option): D1 a question without a verification key inside an active list counts as unverified; D2 api default `any`, CLI default from engine.json `verified`.

# TASK-078 item 1 - REQ-0024 solve gate (draft for docs/design/phase-78-<slug>.md)
Suggested slug: `verified-solve-gate`. Q1 fixed: gate at the bridge (ingest `--exam-out`); solve prompts, SOLVE_OUT, decide logic untouched (AC4).

## Plan modes
solve: unchanged (prompts, SOLVE_OUT, decide). ingest `--exam-out`: gate only when the document carries verification data; single-source and pipeline plans with none are byte-identical. result.json gains optional keys only when something is skipped.

## Facts (where things live)
- Status per question: `doc["questions"][i]["verification"]["status"]`, enum `VERIFY_STATUSES = unverified|verified|needs_review|rejected` (src/exam_engine/ingest/schema.py:12, :39-41). Optional `reasons` list.
- Refined questions (`doc["refined"]`, DGNL) carry no verification today (refine.py has none).
- Bridge: `to_exam_text` api.py:62-104 -> `_from_refined` :237 (via :73-74), `_from_questions` :320 (via :95-96); exam-format Markdown returned verbatim at :85-86.
- Provenance rows: `assembly()` api.py:287-317, written by cli.py:549-556 to `<exam>.assembly.json`; planrun.py:236-240 copies it to `<plan>/input/assembly.json`.
- Only CLI caller: `ingest --exam-out` cli.py:540-556 (not `solve`; brief's "cli ~546 solve" is ingest_main). Other caller: inspect.py:152 (`assembly`, config without the key).
- Result: engine.build_result engine.py:385-404; exit code :479 counts only `result["questions"]` -> skipped never affect it. Report totals reporter.py:168. Schema summary schemas/result.schema.json:376 (no additionalProperties:false).

## Pass rule (`min_verification`)
| level | passes | skipped |
|---|---|---|
| `verified` (engine.json default) | verified | unverified, needs_review, rejected |
| `any` | verified, unverified, needs_review | rejected (always) |
- Gate active only when at least one question of the selected list has a `verification` key. Inside an active list, a question without the key counts as `unverified`.
- No verification anywhere -> gate is a no-op (legacy docs, DGNL refined, md).
- Other value -> argparse `choices` refuses it at the CLI; `api` raises `ValueError("min_verification: ...")`.
- api default when the key is absent from `config` = `any` (no behaviour change for api callers/tests, e.g. test_ingest_schema_q.py:68-69 and inspect.py:152). The `verified` default is a CLI policy that comes from engine.json.

## Design
### 78.1 gate helper (owner: ingest/api.py, new `_gate(qs, config) -> (keep_idx list, skipped list)`)
- `skipped` item: `{"printed": str, "status": str, "reasons": [str]}`. `reasons` = the question's `verification.reasons`, or `[]`.
- `printed` uses the same numbering as `assembly` rows (`n` / `s<sec>.<n>` / refined `id`).
- Filter after context sharing: `_selected_questions` :277 and `_selected_refined` (~:225) compute ctx/why on the full list, then drop the skipped indices. A skipped group carrier still passes its shared passage and figures to kept members (76.4).
- `_from_questions`: the renum check and `_printed` :326-332 run on the kept list. Kept questions keep their `n`, so the "printed numbers:" line maps positions to printed numbers.
- `_from_refined`: `first`/offset line :248-252 is computed on the kept list. If kept ids are not contiguous, the offset line is wrong. Fix: when the gate dropped any refined question, emit the "printed numbers: k=id" form (reuse the `_printed` wording) instead of the N + offset line. Without a drop, output is byte-identical.
- All questions skipped -> `IngestError("no_questions", "all N question(s) below min_verification=<lvl>")` (exit 2, nothing solved).
### 78.2 assembly + sidecar (owner: api.assembly :287, cli.py:540-556)
- `assembly(doc, config)` applies the same `_gate`, so rows stay aligned with exam positions.
- New `api.skipped(doc, config) -> list` (same selection) for the CLI.
- cli ingest: new flag `--min-verification {verified,any}`, default `settings.load_config("engine").get("min_verification", "verified")`; set `cfg2["min_verification"]`.
- If the list is non-empty, write `"skipped": [...]` into the existing `assembly/1` sidecar (key added only when non-empty) and print one `WARN: skipped_unverified: q<printed> <status>` per item to stderr.
- config/engine.json: add `"min_verification": "verified"`. No solve cfg reads it, so plan config.json and the solve cache keys do not change.
### 78.3 result.json + report (owner: engine.build_result :385, reporter.build_markdown :168, schemas/result.schema.json)
- engine reads `exam_path + ".assembly.json"` key `skipped`. Missing or unreadable file -> `[]`, never raises (same tolerance as cli.py:1423).
- When non-empty: top-level `"skipped_unverified": [{printed, status, reasons}]` and `summary["skipped_unverified"] = n`. Both keys are present only when n > 0, so existing result.json files stay byte-identical.
- Skipped items are not in `questions` -> no PASS/FAIL/UNCERTAIN, metrics untouched, exit code :479 unchanged (AC3).
- reporter: after Totals, when present, `- Skipped (unverified): N` plus one line per item `printed X: <status> (<reasons>)`.
- schema: optional `skipped_unverified` (array of object) at top level and an integer in summary.
- No change to solver.py, verifier.py, decide, prompts/, SOLVE_OUT (AC4).

## Backward compatibility (explicit)
- Exam-format Markdown files: returned at api.py:86 before any gate. Byte-identical; no sidecar.
- Docs without verification data (all current PDFs/DOCX, DGNL `--refined` flow): gate no-op. Exam text, assembly.json and result.json byte-identical.
- Byte-identity checks:
  - unit golden test (T6, T7);
  - real `cmp`: re-run `ingest ... --refined <DGNL doc> --exam-out work/TASK-078/exam.md`, then `cmp` it, and its `.assembly.json`, against an existing `plans/<dgnl run>/input/exam.md` and `input/assembly.json` (main picks the plan; $0).

## Failure modes
| Failure | Response | Operator sees |
|---|---|---|
| all questions gated | IngestError no_questions, exit 2 | ERROR line with level |
| sidecar missing/corrupt at solve | skipped = [] | no skipped lines (same as today) |
| exam.md edited after ingest (sidecar stale) | skipped list still reported | listed as-is (risk, see below) |
| bad level | argparse error, exit 2 | usage line |

## Unit tests (tests/unit/test_solve_gate.py, stdlib, $0)
- T1 `_gate` table: each of the 4 statuses x {verified, any}. `rejected` is skipped at both levels.
- T2 AC1 mock: doc q1 verified, q2 needs_review, q3 rejected; run ingest --exam-out then `solve --mock`.
  - exam text holds q1 only;
  - the mock is called with a prompt containing only q1's text (call count = the 1-question run's count; q2/q3 text absent from every prompt);
  - result.json `summary.skipped_unverified == 2` and the statuses are listed;
  - report.md has the Skipped line.
- T3 AC2 restore: `--min-verification any` -> q1+q2 solved, q3 still skipped (`rejected`). engine.json value `any` gives the same result (patch load_config).
- T4 AC3: the T2 result has fail == 0 for skipped ids; pass+fail+uncertain == len(questions) == 1; exit code is the same as for a 1-question run.
- T5 carrier: a group carrier with needs_review is skipped; a kept member still has the shared passage.
- T6 backward compat:
  - a no-verification doc gives the same to_exam_text and assembly at both levels as without the key (PDF path, refined path, exam-format md);
  - the sidecar has no `skipped` key;
  - build_result has no new keys.
- T7 golden: existing golden/clean tests (test_clean_golden.py, test_ingest_refine.py, test_assembly.py) pass unchanged. test_ingest_schema_q.py:68 stays green (api default `any`).
- T8 AC4 guard: `git diff --stat` touches no solver.py/verifier.py/prompts/ (verifier row).
- T9 refined gap: refined ids 61, 63 kept, 62 gated -> the printed-numbers line is correct and no offset line appears.

## Risks
- A stale sidecar next to a hand-edited exam.md reports skipped items that the file no longer lacks. Accept: the sidecar is written by the same ingest run (same as structure flags 69.4).
- inspect report (inspect.py:152) shows ungated rows. Accept, or pass the engine.json level (main decides; recommend leaving it).
- Mixed docs (some questions without `verification`): treated as unverified -> skipped at default. Safer for fidelity; needs main's OK (Decision D1).

## Decisions for main
- D1 (pick ONE): missing key inside an active list = unverified (recommended) | = pass.
- D2 (pick ONE): api default `any` + CLI default from engine.json `verified` (recommended; keeps api callers and test_ingest_schema_q byte-identical) | api default `verified`.

## Defects
- none

## Out of scope
- Producing verification statuses (REQ-0022/0025); image-only gate; changing solve exit codes.

Nova
