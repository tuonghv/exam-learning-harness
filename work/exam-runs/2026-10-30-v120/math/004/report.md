# Exam report: Mathematics

- Exam: Mathematics, Grade 12, High School Graduation, task Short Answer, mode Solve
- Run: claude-p (sonnet), 2 call(s), cost $0.0374
- Totals: PASS 0, FAIL 1, UNCERTAIN 0, unresolved 1
- Points: 1 / 1

## Question 1

- Answer: 37/42
- Verdict: **FAIL**
- Reason: check_failed: computed
- Evidence: key match
- Score: 1 / 1 (official_key)

| Check | Result | Independent | Detail |
| --- | --- | --- | --- |
| format | pass | no | answer holds a number |
| computed | fail | yes | arithmetic only: 1 - 10/84 = 0.880952381, answer 37 |
| quote | pass | no | verbatim in passage/question: Một hộp chứa 5 viên bi đỏ và 4 viên bi xanh |
| quote | pass | no | verbatim in passage/question: Lấy ngẫu nhiên đồng thời 3 viên bi từ hộp |
| key_match | pass | yes | matches the key |

### QA findings

- deterministic / computed: arithmetic only: 1 - 10/84 = 0.880952381, answer 37

### Explanation

Biến cố 'có ít nhất một bi xanh' là biến cố đối của 'cả 3 viên đều đỏ', nên P = 1 - P(3 đỏ) = 1 - 10/84 = 74/84 = 37/42. 37 và 42 nguyên tố cùng nhau (37 là số nguyên tố không chia hết 42), nên phân số đã tối giản.

### Solution

1. Số cách lấy 3 viên bất kỳ từ 9 viên: C(9,3) = 84, nên không gian mẫu có 84 phần tử.
2. Biến cố đối: cả 3 viên đều đỏ, số cách là C(5,3) = 10.
3. Xác suất của biến cố đối là 10/84 = 5/42.
4. Xác suất cần tìm: 1 - 5/42 = 37/42.

### Uncertainty

low: Bài xác suất cổ điển đơn giản, hai cách tính cho cùng kết quả.
