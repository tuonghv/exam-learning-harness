# Exam report: Tin hoc

- Exam: Tin hoc, Grade 12, High School Graduation, task Short Answer, mode Solve
- Run: claude-p (sonnet), 2 call(s), cost $0.0298
- Totals: PASS 1, FAIL 0, UNCERTAIN 0, unresolved 0
- Points: 1 / 1

## Question 1

- Answer: 62 host
- Verdict: **PASS**
- Reason: independent check passed and reviewer agrees
- Evidence: code oracle
- Score: 1 / 1 (official_key)

| Check | Result | Independent | Detail |
| --- | --- | --- | --- |
| computed | pass | yes | arithmetic only: 2*​*(32-26) - 2 = 62, answer 62 |
| quote | pass | no | verbatim in passage/question: 192.168.10.0/26 |
| ai_review | pass | no | reviewer: agree |
| key_match | pass | yes | matches the key |

### Explanation

Số host tối đa = 2^(32-26) - 2 = 62, có thể gán từ 192.168.10.1 đến 192.168.10.62. Nếu không trừ 2 địa chỉ đặc biệt sẽ ra 64 là sai theo yêu cầu đề. Nếu nhầm số bit host (ví dụ 2^5 - 2 = 30 hoặc 2^7 - 2 = 126) thì tương ứng /27 hoặc /25, không phải /26.

### Solution

1. Biểu diễn: địa chỉ IPv4 32 bit, tiền tố /26 nghĩa là 26 bit mạng, số bit host = 32 - 26 = 6.
2. Tổng số địa chỉ trong mạng con = 2^6 = 64 (từ 192.168.10.0 đến 192.168.10.63).
3. Trừ địa chỉ mạng (192.168.10.0) và địa chỉ quảng bá (192.168.10.63): 64 - 2 = 62.

### Uncertainty

low: Phép tính chuẩn về chia mạng con IPv4, đề nêu rõ không tính địa chỉ mạng và quảng bá.
