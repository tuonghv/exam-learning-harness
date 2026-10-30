# Exam report: Tin hoc

- Exam: Tin hoc, Grade 12, High School Graduation, task Multiple Choice, mode Solve
- Run: claude-p (sonnet), 2 call(s), cost $0.0313
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
| quote | pass | no | verbatim in passage/question: while i < 10: |
| ai_review | pass | no | reviewer: agree |
| key_match | pass | yes | matches the key |

### Explanation

B. 12: đúng, s = 1 + 4 + 7. A. 22: sai, tương ứng cộng thêm cả i = 10 (và 1+4+7+10 = 22), nhưng i = 10 không thỏa i < 10 nên không được cộng. C. 5: sai, mới chỉ chạy 2 lượt (1+4). D. 10: sai, là giá trị cuối của i, không phải của s.

### Solution

1. Biểu diễn: s là tổng tích lũy các giá trị i; i bắt đầu từ 1, tăng 3 mỗi lượt, lặp khi i < 10.
2. Bảng theo dõi (i trước lượt, s sau lượt, i sau lượt): i=1 -> s=1, i=4; i=4 -> s=5, i=7; i=7 -> s=12, i=10.
3. Khi i = 10 thì điều kiện i < 10 sai, vòng lặp dừng. Vậy s = 1 + 4 + 7 = 12.

### Uncertainty

low: Vòng lặp ngắn, chỉ 3 lượt, dễ theo dõi bằng tay.
