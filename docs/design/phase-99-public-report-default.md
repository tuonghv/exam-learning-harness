# Phase 99: default student report (`solution_public-report`) and all-only pack

Task: TASK-099 · REQ-0106 (RAW-00300..313)

## Goal
- Every report run writes the student-facing report by default; file kind `solution_public-report`
  (user's name: `dgnl2025_all_solution_public-report_run-20261112-053241`).
- A multi-subject pack (report-pack / publish) writes only `all` reports; no per-subject human reports
  (e.g. no `dgnl2025_science_answer-sheet_...`).

## Plan modes
No effect on single-source or pipeline plan files: only report output names and the pack file set change; solve inputs untouched.

## Design (reuse first)
1. Registry `config/report_kinds.json`: rename the uncommitted kind `public` to `solution_public-report`
   (ext md, pdf, optional html; scope both). Add per-kind flag `"pack_subject": false` on `answer-sheet`,
   `solution-report`, `solution_public-report`: in a multi-subject pack these are not written per subject.
2. `report_kinds.name/parse`: the kind may hold `_` (registered kinds only). `parse` splits exam = first
   part, subject = second, run = last, kind = the joined middle; the round-trip `name()` check stays.
   Same rule in `tools/check_report_pack.py:parse_name`.
3. `report_kinds.expected(..., pack=True)`: skips per-subject names of kinds with `pack_subject: false`.
4. `report_pack.build_pack`: builds each subject in a temp dir under out_dir (or removes the per-subject
   human files after `report_build.build`), keeps per-subject metrics/result-data/run-log, writes
   `all` solution-report + `all` solution_public-report (md, pdf via `_pdf_siblings`).
5. `report_build.build` (single plan): keeps writing `<exam>_<subject>_solution_public-report_<run>`.
6. Docs: `docs/guide/report-kinds.md` table + one line on the pack rule.

## Not changed
Solver, plans, result JSON, learning-report (only with `--view learn`), score files.

## Newer features kept
Highlighted answer line (`.ans` in md2html), standard run names `run-YYYYMMDD-HHMMSS`.

## Tests
`tests/unit/test_report_kinds.py` (parse of an underscore kind, expected(pack=True)),
`tests/unit/test_overlay.py` / pack tests updated to the all-only file set; full `python3 -m unittest`.

## Verification
Re-run dgnl2025, dgnl2026, dhqg2024 packs ($0, no model call); `tools/check_report_pack.py` passes; grep the
public md for `Đáp án` (present) and `Trạng thái|Độ nghi ngờ|Bằng chứng|Kiểm tra` (absent).
