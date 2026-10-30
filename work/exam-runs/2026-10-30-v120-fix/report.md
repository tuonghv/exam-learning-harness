# Benchmark report

2026-10-30, model sonnet, prompts v1.2.0. Measured, not claimed: 15 items, pass 11 / fail 1 / uncertain 3 / unresolved 4, 30 calls, $0.53.

## Per subject

| Subject | Items | Pass | Fail | Uncertain | Unresolved |
|---|---|---|---|---|---|
| english | 3 | 3 | 0 | 0 | 0 |
| informatics | 3 | 3 | 0 | 0 | 0 |
| literature | 3 | 0 | 0 | 3 | 3 |
| math | 3 | 3 | 0 | 0 | 0 |
| physics | 3 | 2 | 1 | 0 | 1 |

## Per question

| Item | Q | Answer | Verdict | Points | Checked by | Attempts |
|---|---|---|---|---|---|---|
| english/003 | 1 | B | PASS | 1/1 | key match | 1 |
| english/004 | 1 | b-d-a-e-c | PASS | 1/1 | key match | 1 |
| english/005 | 1 | A | PASS | 1/1 | key match | 1 |
| informatics/003 | 1 | B | PASS | 1/1 | key match | 1 |
| informatics/004 | 1 | 3 | PASS | 1/1 | key match | 1 |
| informatics/005 | 1 | 62 host | PASS | 1/1 | key match | 1 |
| literature/003 | 1 | Open | UNCERTAIN | None/None | claude review only | 1 |
| literature/004 | 1 | Open | UNCERTAIN | None/None | claude review only | 1 |
| literature/005 | 1 | Open | UNCERTAIN | None/None | claude review only | 1 |
| math/003 | 1 | A | PASS | 1/1 | key match | 1 |
| math/004 | 1 | 37/42 | PASS | 1/1 | key match | 1 |
| math/005 | 1 | sqrt(2) | PASS | 1/1 | key match | 1 |
| physics/003 | 1 | B | FAIL | 1/1 | key match | 2 |
| physics/004 | 1 | 9 điểm | PASS | 1/1 | key match | 1 |
| physics/005 | 1 | 1,8.10^-19 J (làm tròn đến 2 c | PASS | 1/1 | key match | 1 |

## Failures (read the cause from evidence)

- physics/003 Q1: answer B, reason check_failed: quote, findings ['quote', 'malformed_output']
