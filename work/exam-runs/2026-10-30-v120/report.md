# Benchmark report

2026-10-30, model sonnet, prompts v1.2.0. Measured, not claimed: 15 items, pass 6 / fail 6 / uncertain 3 / unresolved 9, 31 calls, $0.57.

## Per subject

| Subject | Items | Pass | Fail | Uncertain | Unresolved |
|---|---|---|---|---|---|
| english | 3 | 2 | 1 | 0 | 1 |
| informatics | 3 | 2 | 1 | 0 | 1 |
| literature | 3 | 0 | 0 | 3 | 3 |
| math | 3 | 1 | 2 | 0 | 2 |
| physics | 3 | 1 | 2 | 0 | 2 |

## Per question

| Item | Q | Answer | Verdict | Points | Checked by | Attempts |
|---|---|---|---|---|---|---|
| english/003 | 1 | B | PASS | 1/1 | key match | 1 |
| english/004 | 1 | b-d-a-e-c | FAIL | 1/1 | key match | 2 |
| english/005 | 1 | A | PASS | 1/1 | key match | 1 |
| informatics/003 | 1 | B | PASS | 1/1 | key match | 1 |
| informatics/004 | 1 | 3 | PASS | 1/1 | key match | 2 |
| informatics/005 | 1 | 62 host | FAIL | 0/1 | key match | 1 |
| literature/003 | 1 | Open | UNCERTAIN | None/None | claude review only | 1 |
| literature/004 | 1 | Open | UNCERTAIN | None/None | claude review only | 1 |
| literature/005 | 1 | Open | UNCERTAIN | None/None | claude review only | 1 |
| math/003 | 1 | A | PASS | 1/1 | key match | 1 |
| math/004 | 1 | 37/42 | FAIL | 1/1 | key match | 2 |
| math/005 | 1 | sqrt(2) | FAIL | 1/1 | key match | 2 |
| physics/003 | 1 | B | PASS | 1/1 | key match | 1 |
| physics/004 | 1 | 9 điểm | FAIL | 0/1 | key match | 1 |
| physics/005 | 1 | 1.8e-19 J (làm tròn đến 2 chữ  | FAIL | 0/1 | key match | 2 |

## Failures (read the cause from evidence)

- english/004 Q1: answer b-d-a-e-c, reason check_failed: quote, findings ['quote', 'quote', 'quote', 'quote', 'quote']
- informatics/005 Q1: answer 62 host, reason differs_from_key, findings ['differs_from_key']
- math/004 Q1: answer 37/42, reason check_failed: computed, findings ['computed']
- math/005 Q1: answer sqrt(2), reason check_failed: computed, findings ['computed']
- physics/004 Q1: answer 9 điểm, reason differs_from_key, findings ['differs_from_key']
- physics/005 Q1: answer 1.8e-19 J (làm tròn đến 2 chữ số có nghĩa), reason differs_from_key, findings ['computed', 'differs_from_key']
