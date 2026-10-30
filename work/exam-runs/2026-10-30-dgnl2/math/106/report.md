# Exam report: Mathematics

- Exam: Mathematics, Grade 12, University Entrance (DGNL), task Multiple Choice, mode Solve
- Run: claude-p (sonnet), 4 call(s), cost $0.0653
- Totals: PASS 1, FAIL 0, UNCERTAIN 0, unresolved 0
- Points: 1 / 1

## Question 1

- Answer: B
- Verdict: **PASS**
- Reason: independent check passed and reviewer agrees
- Evidence: key match
- Score: 1 / 1 (official_key)

| Check | Result | Independent | Detail |
| --- | --- | --- | --- |
| format | pass | no | single letter A-D |
| computed | unknown | no | arithmetic only: answer has no number |
| ai_review | pass | no | reviewer: agree |
| key_match | pass | yes | matches the key |

### Explanation

Đáp án B vì P(H1|D)=3/5. A (3/10) sai vì đó chỉ là P(H1 và D), chưa chia cho P(D). C (3/7) sai vì là tỉ lệ 3/(3+4) giữa số bi đỏ hai hộp, bỏ qua việc mỗi hộp có số bi khác nhau (5 và 10). D (2/5) sai vì là P(D|H2), cũng bằng P(H2|D) nên là xác suất lấy từ hộp II, không phải hộp I.

### Solution

1. Gọi H1 là biến cố chọn hộp I, H2 là chọn hộp II, D là lấy được bi đỏ. P(H1)=P(H2)=1/2.
2. P(D|H1)=3/5; P(D|H2)=4/10=2/5.
3. P(D)=1/2*3/5+1/2*2/5=3/10+2/10=1/2.
4. Theo công thức Bayes: P(H1|D)=(1/2*3/5)/(1/2)=3/5.

### Uncertainty

low: Bài Bayes cơ bản, số liệu rõ ràng và có hai cách tính cho cùng kết quả.
