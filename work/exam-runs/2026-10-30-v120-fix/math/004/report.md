# Exam report: Mathematics

- Exam: Mathematics, Grade 12, High School Graduation, task Short Answer, mode Solve
- Run: claude-p (sonnet), 2 call(s), cost $0.0293
- Totals: PASS 1, FAIL 0, UNCERTAIN 0, unresolved 0
- Points: 1 / 1

## Question 1

- Answer: 37/42
- Verdict: **PASS**
- Reason: independent check passed and reviewer agrees
- Evidence: code oracle
- Score: 1 / 1 (official_key)

| Check | Result | Independent | Detail |
| --- | --- | --- | --- |
| format | pass | no | answer holds a number |
| computed | pass | yes | arithmetic only: 1 - 10/84 = 0.880952381, answer 0.880952381 |
| ai_review | pass | no | reviewer: agree |
| key_match | pass | yes | matches the key |

### Explanation

Dùng biến cố đối: P(ít nhất một bi xanh) = 1 - P(cả 3 bi đỏ). C(9,3) = 84 và C(5,3) = 10 nên P(cả 3 đỏ) = 5/42, suy ra đáp án 37/42. Phân số 37/42 đã tối giản vì 37 là số nguyên tố và không chia hết 42.

### Solution

1. Không gian mẫu: chọn 3 viên từ 9 viên, số phần tử n = C(9,3) = 84.
2. Biến cố đối: không có viên bi xanh nào, tức cả 3 viên đều đỏ. Số cách = C(5,3) = 10.
3. Xác suất biến cố đối = 10/84 = 5/42.
4. Xác suất cần tìm = 1 - 5/42 = 37/42.

### Uncertainty

low: Bài xác suất tổ hợp cơ bản, hai cách tính cho cùng kết quả.
