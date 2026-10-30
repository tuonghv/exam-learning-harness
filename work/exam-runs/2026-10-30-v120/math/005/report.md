# Exam report: Mathematics

- Exam: Mathematics, Grade 12, High School Graduation, task Short Answer, mode Solve
- Run: claude-p (sonnet), 2 call(s), cost $0.0383
- Totals: PASS 0, FAIL 1, UNCERTAIN 0, unresolved 1
- Points: 1 / 1

## Question 1

- Answer: sqrt(2)
- Verdict: **FAIL**
- Reason: check_failed: computed
- Evidence: key match
- Score: 1 / 1 (official_key)

| Check | Result | Independent | Detail |
| --- | --- | --- | --- |
| format | pass | no | answer holds a number |
| computed | fail | yes | arithmetic only: (10/5)*​*0.5 = 1.414213562, answer 2 |
| quote | pass | no | verbatim in passage/question: (1 + 2i)z = 3 - i |
| key_match | pass | yes | matches the key |

### QA findings

- deterministic / computed: arithmetic only: (10/5)*​*0.5 = 1.414213562, answer 2

### Explanation

Dùng tính chất |a*b| = |a|*|b|. Ghi chú review cho đáp án 2 là không khớp: chính phép tính (10/5)*​*0.5 = 1.414... cho sqrt(2), không phải 2. Đáp án 2 chỉ đúng nếu quên lấy căn, tức là tính |z|^2 thay vì |z|.

### Solution

1. Tập xác định: z là số phức, 1 + 2i khác 0 nên phương trình có nghiệm duy nhất z = (3 - i)/(1 + 2i).
2. Lấy môđun hai vế: |1 + 2i| * |z| = |3 - i|, với |1 + 2i| = sqrt(5) và |3 - i| = sqrt(10).
3. Suy ra |z| = sqrt(10)/sqrt(5) = sqrt(2).

### Uncertainty

low: Phép tính ngắn, đã kiểm tra bằng hai cách.
