# Exam report: Mathematics

- Exam: Mathematics, Grade 12, University Entrance (DGNL), task Multiple Choice, mode Solve
- Run: claude-p (sonnet), 2 call(s), cost $0.0373
- Totals: PASS 1, FAIL 0, UNCERTAIN 0, unresolved 0
- Points: 1 / 1

## Question 1

- Answer: A
- Verdict: **PASS**
- Reason: independent check passed and reviewer agrees
- Evidence: key match
- Score: 1 / 1 (official_key)

| Check | Result | Independent | Detail |
| --- | --- | --- | --- |
| format | pass | no | single letter A-D |
| computed | unknown | no | arithmetic only: answer has no number |
| quote | pass | no | verbatim in passage/question: Biết bi lấy ra từ hộp II có màu đỏ, xác suất để bi chuyển từ hộp I sang hộp II c |
| ai_review | pass | no | reviewer: agree |
| key_match | pass | yes | matches the key |

### Explanation

A. 3/7: đúng, là P(D1|D2) theo công thức Bayes. B. 5/8: sai, đây là P(D2), xác suất toàn phần của việc lấy được bi đỏ từ hộp II, chưa phải xác suất có điều kiện. C. 15/56: sai, đây là xác suất đồng thời P(D1 và D2), chưa chia cho P(D2). D. 4/7: sai, đây là P(D2|T1), tức xác suất lấy được bi đỏ từ hộp II khi bi chuyển sang là bi trắng, không phải xác suất cần tìm.

### Solution

1. Gọi D1 là biến cố bi chuyển sang có màu đỏ, T1 là biến cố bi chuyển sang có màu trắng, D2 là biến cố bi lấy ra từ hộp II có màu đỏ. P(D1) = 3/8, P(T1) = 5/8.
2. Nếu chuyển bi đỏ: hộp II có 5 đỏ, 2 trắng (7 bi), nên P(D2|D1) = 5/7.
3. Nếu chuyển bi trắng: hộp II có 4 đỏ, 3 trắng (7 bi), nên P(D2|T1) = 4/7.
4. Công thức xác suất toàn phần: P(D2) = 3/8 * 5/7 + 5/8 * 4/7 = 15/56 + 20/56 = 35/56 = 5/8.
5. Công thức Bayes: P(D1|D2) = (15/56) / (35/56) = 15/35 = 3/7.

### Uncertainty

low: Bài Bayes cơ bản, các phép tính đã đối chiếu bằng hai cách.
