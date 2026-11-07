# Phase 81 - Solve De-thi-mau-DHQG-HCM-2024 end to end (REQ-0086) - draft for docs/design/phase-81-dhqg2024-solve.md
Task: TASK-081 · Status: draft · Cap 5 USD (user, 2026-11-07, REQ-0086 progress log)

## Goal
Run the current engine on `input/dgnl/De-thi-mau-DHQG-HCM-2024.pdf`: free ingest + cost estimate, refine all pages,
4 section solves, answers by printed number with status/doubt (no key -> no score), detailed solutions .md + PDF.
Run task, no code change (same shape as phase-80). Reuse: `docs/guide/dgnl-real-exam.md` §Steps 1-6 verbatim.

## Constraints
- Outputs only in git-ignored `plans/dhqg2024-t81/` (doc, parts, exam files, runs, cache) and `reports/dhqg2024-t81/`.
  Never write into `plans/dhqg2024/` or `reports/dhqg2024/` (prior 2026-11-05 run, kept as agreement oracle).
- No question text in tracked files; report cites printed number, page, status, doubt only.
- Paid steps run by main only, each with `--max-cost-usd`; running total kept in `plans/dhqg2024-t81/cost.tsv`.
- Exam-extraction rules: a question cut by a page is one unit; batches overlap by one page so the page before a
  continuation is always selected; `orphan_continuation` -> re-run with page N-1; incomplete -> declined, never guessed.

## Generality
Run only; no code, config or prompt change.

## Known incidents
Prior run of this PDF (REQ-0086 log 2026-11-05): 16 pages, 120 q, refine $0.88, solve $1.49, Science run 0.71 over its
0.50 cap, 8 declined. Phase-80: solve exit 1 = UNCERTAIN without key (not an error); numeric science answers come as
value not letter (map to option when reporting).

## Plan modes
No impact on single-source or pipeline plans: engine and prompts unchanged, only runs.

## Design
P=`input/dgnl/De-thi-mau-DHQG-HCM-2024.pdf`, D=`plans/dhqg2024-t81`, R=`reports/dhqg2024-t81`, X=`python3 -I scripts/exam.py`.

### 81.1 Free ingest + cost estimate (AC1, $0)
- `X ingest P --out D/doc.json`; record page count, printed-page offset, section boundaries (1-30, 31-60, 61-90, 91-120 expected; confirm from doc).
- `X ingest-refine P --pages 1-<N> --all-pages --dry-run` -> refine estimate (expect ~$0.04/page, ~$0.64-0.9).
- Solve estimate: prior actual $1.49 (0.3-0.45/section); budget 1.0/section cap.
- Write `D/estimate.txt` (refine + solve + total). Gate: total > 5 USD -> STOP, SendMessage user via main, no paid call.

### 81.2 Small slice first (~$0.08)
- `X ingest-refine P --pages 1-2 --all-pages --real --max-cost-usd 0.2 --cache D/cache --out D/parts/1-2.json`.
- Inspect: question count, `needs_review`, warnings; check one page by eye vs. output. Fix nothing in code; if broken -> STOP, report.

### 81.3 Refine remaining pages (AC2)
- Batches of 4-5 pages, overlapping one page: 2-6, 6-10, 10-14, 14-N (adjust to N). Each `--real --max-cost-usd 0.4
  --cache D/cache` (cache makes overlap pages and re-runs free). A failed batch: re-run that range alone.
- Merge `refined.questions` into `D/merged.json` in page order (guide step 3; overlap duplicates: exact duplicate ids
  dropped as in phase-80, cut questions kept for join).
- `X ingest-inspect` on merged: list extraction suspects and `missing_text`; each re-run (with page N-1) or explained.

### 81.4 Section exam files + solve (AC2)
- Per section S in Vietnamese 1-30, English 31-60, Math 61-90, Science 91-120:
  `X ingest P --refined D/merged.json --questions <range> --meta Subject=<S> --meta Level="Grade 12" --meta "Exam
  type=University Entrance (DGNL)" --meta "Task=Multiple Choice" --meta Mode=Solve --meta Language=vi --exam-out D/e-<S>.md`
- Check each exam file has 30 questions before solving.
- `X solve D/e-<S>.md --real --max-cost-usd 1.0 --no-pdf --out D/run-<S>` (prior Science overran 0.50; 1.0 keeps total <= 5).
- Exit 1 with status UNCERTAIN is expected (no key).

### 81.5 Answers table (AC2)
- `D/answers.tsv` columns: printed_no, section, page, answer_letter, status, doubt, note (declined reason / value->letter map).
- Printed number = section offset + index. Numeric values mapped to option letter by hand; note it.
- Agreement oracle: diff vs `plans/dhqg2024/answers.tsv` (prior run); list disagreements as doubt, never pick by guess.

### 81.6 Detailed solutions .md + PDF (AC3)
- Per section: `X report D/run-<S>/result.json --out R/<S> --view learn` -> report.md + report.pdf (weasyprint).
  Also default `--view sheet` if main wants an answer sheet. Confirm `report pdf -> ...` lines printed.
- If weasyprint missing: report md written, PDF line absent -> BLOCKED to user (install), do not switch renderer.

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| Estimate > 5 USD | stop before any paid call | estimate.txt + question to user |
| Batch call fails / invalid reply | re-run that page range (cache) | refine exit code, warning |
| `orphan_continuation` | re-run with page N-1 included | warning in refine output |
| Question incomplete | `[Incomplete: missing_text]`, solver declines | declined row in answers.tsv |
| Section run hits cap | run stops; cost so far recorded | re-run only if total stays <= 5 |
| Section count != 30 | stop before solve | ingest-inspect / exam file count |

## Unit tests
None (no code change). Gate: `python3 -I -m unittest discover -s tests/unit` still passes (unchanged tree).

## Verification
| Item | command -> expected | tier |
|---|---|---|
| 81.1 | `cat D/estimate.txt` -> refine+solve+total, total <= 5 | free |
| 81.2 | `D/parts/1-2.json` has questions of p1-2, no crash | ~$0.08 |
| 81.3 | merged has 120 printed numbers 1-120; suspects list empty or each explained | ~$0.6-0.8 |
| 81.4 | 4 `run-<S>/result.json`; sum of costs + refine <= 5 (`D/cost.tsv`) | ~$1.5-2 |
| 81.5 | `wc -l D/answers.tsv` = 121; every row has status+doubt; diff vs prior listed | free |
| 81.6 | `ls R/*/report.{md,pdf}` -> 4 md + 4 pdf, learn view has explanations | free |
| scope | `git status --porcelain` shows no new tracked file under plans/ or reports/ | free |

Crosscheck (crosscheck_required): verifier reads PDF pages of every declined/high-doubt number independently and
recomputes 10 math answers by hand; counts reconciled 120 = answered + declined.

## Evidence (evidence_required=false; summary in report only)
estimate.txt, cost.tsv, answers.tsv, diff vs prior, report.{md,pdf} list, ingest-inspect suspects list (all untracked);
report `docs/report/phase-81-dhqg2024-solve.md`: counts, cost, declined/doubt numbers, disagreements with prior run.

## Decisions
- Fresh run under t81 dirs - reuse prior `plans/dhqg2024` - prior used an older engine and libreoffice PDF; REQ asks current engine + report command.
- Solve cap 1.0/section - 0.5 - prior Science overran 0.50.
- One-page overlap batches + cache - disjoint batches - guarantees page N-1 for continuations at small cost.

## Out of scope
Engine fixes (value->letter mapping, renderer fallback); scoring (no answer file).

## Defects
none (no code/content touched). Note: `scripts/exam.py solve --dry-run` estimate output not checked by designer; main confirm via `--help`/dry-run in 81.1.

Nova
