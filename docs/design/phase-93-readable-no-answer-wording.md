PROGRESS: COMPLETE
SKILLS: design, token-efficiency
# Phase 93 - readable no-answer wording 
Task: TASK-093 · REQ-0100 · Status: draft
## Goal
Solution report md/pdf (per subject + combined) never prints the raw token `none`/`(none)`; declined, unevidenced, unscored lines read as localized phrases (vi/en). Data files unchanged. Proof: `grep -cw none` on the new `*_solution-report_*.md` = 0, checker PASS, counts as before.
## Inventory (old packs: F = dgnl2026/f/run-20261107-221047, T = dhqg2024/t81/run-20261108-055609)
| Source | Current text | F (all md / 4 subj md) | T (all / subj) | New vi | New en |
|---|---|---|---|---|---|
| reporter.py:207 `or "none"` | `**Đáp án: none**` | 1 / 1 | 9 / 9 | `**Đáp án: chưa có đáp án (solver từ chối)**` | `**Answer: no answer (solver declined)**` |
| reporter.py:214 evidence_kind (core/decision.py:51 returns "none"; stored q.evidence_kind same) | `- Bằng chứng: none` | 5 / 5 | 11 / 11 | `- Bằng chứng: không có (chưa có kiểm tra nào đạt)` | `- Evidence: no passed check` |
| reporter.py:216 score (scorer.py:144/147/164 basis "none", points/max None) | `- Điểm: - / - (none)` | 120 / 120 | 120 / 120 | `- Điểm: chưa chấm` | `- Score: not scored` |
| metrics.py:527 via reporter.py:182 (subject md only, Metrics block) | `- accuracy: none` | 0 / 4 | 0 / 4 | `- accuracy: no key` (block is English-only engineering text, shared with CLI) | same |
Totals reconcile: F all 126 = 120+1+5; F subj 130 = 120+1+5+4; T all 140 = 120+9+11; T subj 144 = 120+9+11+4.
Not report text (stay raw, data): answer-table tsv `score` column = basis `none` (120/pack, report_pack.py:149), score-summary json key `"none"` (report_pack.py:65), metrics json, result.json. Learning view (reporter.py:130-133) and answer sheet (reporter.py:61-66) print `—` for declined: no `none`, unchanged.
## Design
### 93.1 Labels (owner: reporter.py:87 LABELS)
Add keys to both langs: `no_answer` vi "chưa có đáp án (solver từ chối)" / en "no answer (solver declined)"; `no_evidence` vi "không có (chưa có kiểm tra nào đạt)" / en "no passed check"; `no_score` vi "chưa chấm" / en "not scored". No en phrase may contain the word `none`.
### 93.2 Question block (owner: reporter.py:_question_block 207/214/216)
- 207: `... or L["no_answer"]` instead of `or "none"`.
- 214: `ek = q.get("evidence_kind") or evidence_kind(q)`; print `L["no_evidence"] if ek == "none" else ek`.
- 216: if `sc.get("points") is None and sc.get("max") is None` print `- <score>: <no_score>`; else unchanged format (basis `none` cannot occur with points, scorer.py:144-164).
- One code path: build_combined_markdown -> _subject_section -> _question_block, so per-subject, combined and pdf (md_to_pdf of the same md) all change.
### 93.3 Metrics line (owner: metrics.py:527)
`"none"` -> `"no key"` in `accuracy:`. Only consumer that reads it: tests/unit/test_run_stats.py:132-188 (asserts keyed values only). No parser of `accuracy: none` in src/tools/.claude.
### 93.4 Data stays raw (no code change; regression-tested)
`decision.evidence_kind`/KINDS keep "none" (test_exam_report.py:160-171); score basis "none" (test_exam_checks.py:175-225, test_exam_run.py:219-339); report_pack tsv/json unchanged; result.json untouched (reporter only reads it).
### 93.5 Parsers still work
- report_kinds.py:178 `_has_text`: `re.match(r"\s*(\*\*|- )?Đáp án", ln)` matches the label prefix only -> with_text unchanged (vi; note it never matched `**Answer` - existing, not this task).
- tools/check_report_pack.py:140/153 count `^### \S+ (\d+)\s*$` headings; declined counted from score-vs-key tsv col 4 == "declined" (line 165-181) - data, unchanged.
- review.py parses its own review pack (Flags:/QA:), not the solution report.
- Declined in md is recognised by `^\*\*(Đáp án|Answer): (.+)\*\*$` with group 2 == LABELS[lang]["no_answer"] (tests use this; no production parser needs it).
### 93.6 Rebuild ($0, main runs; new folders, old kept)
- F: `exam report-pack plans/dgnl2026/f/runs/{20261105-100541-vietnamese,20261105-100543-english,20261105-100543-math,20261105-144607-science2} --exam dgnl2026 --run f --key input/dgnl/De-thi-minh-hoa-2026-Final.answer.txt` (no `--out`: cli.py:458 makes a new reports/dgnl2026/f/run-<id>/).
- T: `exam report-pack plans/dhqg2024/t81/runs/{20261107-005624-vietnamese,20261107-005812-english,20261107-005940-math,20261107-010203-science} --exam dhqg2024 --run t81` (keyless).
- Then `tools/check_report_pack.py <new dir>` PASS each. Expected = previous: F 120 Q, with_text 120/120 all + 30/30 x4, total_correct 113, declined 1 (score-summary json); T 120 Q, with_text 120/120; answer-table tsv byte-identical to old run (diff); `grep -cw none *_solution-report_*.md` = 0 in both new dirs; `grep -c 'chưa chấm'` all md = 120; `chưa có đáp án` F 1 / T 9; `kiểm tra nào đạt` F 5 / T 11.
## Plan modes
- solve / report-build / report-pack: report text only, same function. Answer-sheet, learn view: unaffected. No prompt or cache key touched (render only).
## Failure modes
| Failure | Response | Operator sees |
|---|---|---|
| en phrase contains "none" | unit grep test fails | test name |
| stored evidence_kind None/"" | falls back to evidence_kind(q) as today | label |
| new run overwrites old | cli default makes a fresh run dir; main checks old dir mtime/sha | two run dirs |
| tsv differs from old run | diff non-empty -> stop, report | diff lines |
## Unit tests (tests/unit/test_exam_report.py)
1. vi: declined q (answer None, checks [], score none) -> md contains the 3 vi phrases, `re.search(r"\bnone\b", md, re.I)` is None (build_markdown with metrics fixture, so 93.3 covered).
2. en: same with language en -> en phrases, no `none`.
3. answered q with key_match pass and points 1/1 -> `Evidence: key match`, `Score: 1 / 1 (key)` unchanged.
4. report_kinds._has_text true for a block whose answer line is the new no_answer phrase.
5. metrics.block no-key -> `accuracy: no key`; keyed lines unchanged (existing test_run_stats).
6. report_pack mock (2 plans, 1 declined): tsv rows/`score` column identical to before, solution-report md has no `\bnone\b`.
## Decisions
None needed. Chosen: render-time mapping (data keeps "none") - rejected: change decision/scorer values (breaks tests, result.json schema, run_stats).
## Defects
- D1 (minor, REQ-0100 AC4 wording): "no `none` token in the new runs" cannot hold for data files (tsv score column 120/pack, score-summary json key, metrics json) which AC2 requires unchanged; read AC4 as solution-report md/pdf only. Main to word the AC tick so.
- D2 (minor, observation): F pack has a key but every question prints "chưa chấm" because the per-question score is computed at solve time without a key; pack-level score lives in score-summary. Wording is truthful; filling scores from the pack key is out of scope.
## Out of scope
English-only status/evidence values ("code oracle", "UNCERTAIN", status_reason) localisation; `-` fallbacks for status reason/doubt; _has_text English label.
Nova
