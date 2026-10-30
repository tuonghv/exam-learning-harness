# Exam report: Mathematics

- Exam: Mathematics, Grade 12, High School Graduation, task Short Answer, mode Solve
- Run: claude-p (sonnet), 3 call(s), cost $0.0518
- Totals: PASS 0, FAIL 1, UNCERTAIN 0, unresolved 1
- Points: 0 / 1

## Question 1

- Answer: x = 8 là nghiệm duy nhất; tổng các nghiệm = 8
- Verdict: **FAIL**
- Reason: differs_from_key
- Evidence: code oracle
- Score: 0 / 1 (official_key)

| Check | Result | Independent | Detail |
| --- | --- | --- | --- |
| format | pass | no | answer holds a number |
| computed | pass | yes | arithmetic only: 8 = 8, answer 8 |
| ai_review | pass | no | reviewer: agree |

### QA findings

- score / differs_from_key: answer differs from the key

### Explanation

Nghiệm x = -4 là nghiệm ngoại lai vì làm x + 1 = -3 < 0 và x - 5 = -9 < 0, logarit không xác định. Tổng 4 của hai nghiệm phương trình bậc hai (theo Viete) không phải đáp án vì đã tính cả nghiệm bị loại. Chỉ x = 8 thuộc tập xác định nên tổng các nghiệm của phương trình ban đầu là 8.

### Solution

1. Điều kiện xác định: x + 1 > 0 và x - 5 > 0, suy ra x > 5.
2. Gộp logarit: log_3((x + 1)(x - 5)) = 3, suy ra (x + 1)(x - 5) = 27.
3. Khai triển: x^2 - 4x - 5 = 27, suy ra x^2 - 4x - 32 = 0, nên x = 8 hoặc x = -4.
4. Loại x = -4 vì không thỏa x > 5. Nhận x = 8.
5. Phương trình chỉ có một nghiệm nên tổng các nghiệm = 8.

### Uncertainty

low: Phép giải đơn giản, đã loại nghiệm ngoại lai và thay ngược lại.
