# Exam report: Tin hoc

- Exam: Tin hoc, Grade 12, High School Graduation, task Short Answer, mode Solve
- Run: claude-p (sonnet), 2 call(s), cost $0.0283
- Totals: PASS 0, FAIL 1, UNCERTAIN 0, unresolved 1
- Points: 0 / 1

## Question 1

- Answer: 62 host
- Verdict: **FAIL**
- Reason: differs_from_key
- Evidence: code oracle
- Score: 0 / 1 (official_key)

| Check | Result | Independent | Detail |
| --- | --- | --- | --- |
| computed | pass | yes | arithmetic only: 2*​*(32-26) - 2 = 62, answer 62 |
| quote | pass | no | verbatim in passage/question: 192.168.10.0/26 |
| ai_review | pass | no | reviewer: agree |

### QA findings

- score / differs_from_key: answer differs from the key

### Explanation

Số host tối đa = 2^(32-26) - 2 = 62. Dải host dùng được là 192.168.10.1 đến 192.168.10.62. Không làm tròn vì là số nguyên.

### Solution

1. Biểu diễn: địa chỉ IPv4 32 bit, tiền tố /26 nghĩa là 26 bit mạng, 32 - 26 = 6 bit host.
2. Tổng số địa chỉ trong mạng con = 2^6 = 64.
3. Trừ địa chỉ mạng (192.168.10.0) và địa chỉ quảng bá (192.168.10.63): 64 - 2 = 62.

### Uncertainty

low: Phép tính chuẩn về chia mạng con IPv4, không có chỗ mơ hồ trong đề.
