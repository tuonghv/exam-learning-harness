# Exam report: Mathematics

- Exam: Mathematics, Grade 12, University Entrance (DGNL), task Multiple Choice, mode Solve
- Run: claude-p (sonnet), 2 call(s), cost $0.0361
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
| quote | pass | no | verbatim in passage/question: Biết bi lấy ra từ hộp II có màu đỏ, xác suất để bi đã chuyển từ hộp I sang hộp I |
| ai_review | pass | no | reviewer: agree |
| key_match | pass | yes | matches the key |

### Explanation

A. 15/56: sai, đây chỉ là P(H và R) = 3/8 * 5/7, chưa chia cho P(R). B. 3/7: đúng, là P(H|R) = P(H và R)/P(R). C. 3/8: sai, đây là xác suất tiên nghiệm P(H), chưa dùng thông tin bi lấy ra là đỏ. D. 5/7: sai, đây là P(R|H), tức là đảo ngược điều kiện.

### Solution

1. Gọi H là biến cố bi chuyển sang hộp II có màu đỏ, R là biến cố bi lấy ra từ hộp II có màu đỏ. P(H) = 3/8, P(không H) = 5/8.
2. Nếu bi chuyển là đỏ: hộp II có 5 đỏ, 2 xanh (7 bi), nên P(R|H) = 5/7. Nếu bi chuyển là xanh: hộp II có 4 đỏ, 3 xanh (7 bi), nên P(R|không H) = 4/7.
3. P(R) = 3/8 * 5/7 + 5/8 * 4/7 = 15/56 + 20/56 = 35/56 = 5/8.
4. Công thức Bayes: P(H|R) = (15/56) / (35/56) = 15/35 = 3/7.

### Uncertainty

low: Bài Bayes cơ bản, các bước tính đơn giản và đã kiểm tra bằng hai cách.
