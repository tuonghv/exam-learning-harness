# Phase 146 – Re-solve DGNL 2024/2025/2026 with Opus 5.5 report (TASK-146, REQ-0152)

**Verdict: done.** Paid re-solve approved (RAW-00365, cap $18): $8.65 spent; Opus 5.5 335/359 vs published
Sonnet 331/359 (net +4, all from 2024). Published main runs unchanged; the user decides whether to publish.

## Results (score vs key, dev line `o55`)
| Exam | Published (Sonnet) | Opus 5.5 | Fixed | Lost | Net | Cost |
|---|---|---|---|---|---|---|
| dhqg2024 | 105/119 | 110/119 | 3, 26, 28, 57, 82 | - | +5 | $2.83 |
| dgnl2025 | 113/120 | 113/120 | 59, 107 | 106, 108 | 0 | $2.92 |
| dgnl2026 | 113/120 | 112/120 | 43 | 21, 37 | -1 | $2.90 |

- Inputs: the exact `input/exam.md` of each published plan run (sha256 checked), same image flags, model
  `claude-opus-5-5`, cap $1.45/subject. Packs: `reports/<exam>/o55/run-o55pack` (no PDF).
- 2024 gain: three of the five fixes were questions Sonnet declined (26, 28, 57); Opus answered them correctly.
- 2026 q37 declined by Opus: it judged the item ambiguous (relative clause on "Paris" vs "the museum") and named
  B, the key, as the likely intent. q21 and q43 flipped the same way as the TASK-145 Sonnet re-solve.
- Two 2024 runs stopped on the claude.ai usage limit and were re-run after reset (counted in the cost).

## Reading
2025/2026 differences (±1-2) are within run-to-run noise (TASK-145 saw ±1 with Sonnet alone). The 2024 +5 with
0 lost is a real gain, mostly from answering items Sonnet declined. Option: publish 2024 from `o55` (free).

## Spend
$8.65 of the approved $18.

## Publish (RAW-00367)
User chose to publish 2024 from `o55`: pack `reports/dhqg2024/o55/run-20261117-113346` (110/119) ->
`main: run-20261117-052511 -> run-20261117-113355`. Recipe `config/published_reports.json` rewritten with
`--write-recipe` (only dhqg2024 changed: line o55, o55 plan runs, overlay slice); `rebuild-reports dhqg2024 --dry-run`
passes. 2025 and 2026 stay on their Sonnet runs.
