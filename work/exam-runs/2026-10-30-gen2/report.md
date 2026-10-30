# Benchmark report

2026-10-30, model sonnet, prompts v1.2.0. Measured, not claimed: 5 items, pass 4 / fail 1 / uncertain 0 / unresolved 1, 14 calls, $0.24.

## Per subject

| Subject | Items | Pass | Fail | Uncertain | Unresolved |
|---|---|---|---|---|---|
| math | 5 | 4 | 1 | 0 | 1 |

## Per question

| Item | Q | Answer | Verdict | Points | Checked by | Attempts |
|---|---|---|---|---|---|---|
| math/104 | 1 | 9/11 | PASS | 1/1 | key match | 1 |
| math/105 | 1 | 15 | PASS | 1/1 | key match | 2 |
| math/106 | 1 | x = 8 là nghiệm duy nhất; tổng | FAIL | 0/1 | key match | 2 |
| math/107 | 1 | 7 | PASS | 1/1 | key match | 2 |
| math/108 | 1 | 15 | PASS | 1/1 | key match | 2 |

## Failures (read the cause from evidence)

- math/106 Q1: answer x = 8 là nghiệm duy nhất; tổng các nghiệm = 8, reason differs_from_key, findings ['differs_from_key']
