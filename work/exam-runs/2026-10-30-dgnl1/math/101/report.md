# Exam report: Mathematics

- Exam: Mathematics, Grade 12, University Entrance (DGNL), task Multiple Choice, mode Solve
- Run: claude-p (sonnet), 2 call(s), cost $0.0403
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
| quote | pass | no | verbatim in passage/question: Biết rằng trong 3 viên bi lấy được có ít nhất một viên bi đỏ, xác suất để 3 viên |
| ai_review | pass | no | reviewer: agree |
| key_match | pass | yes | matches the key |

### Explanation

B. 12/37: đúng, bằng 60/185 sau khi rút gọn cho 5. A. 3/11: sai, đây là 60/220, tức xác suất không điều kiện (quên điều kiện có ít nhất một bi đỏ). C. 12/35: sai, đây là 60/175, mẫu số tính nhầm. D. 37/44: sai, đây là 185/220, xác suất của biến cố có ít nhất một bi đỏ, không phải xác suất cần tìm.

### Solution

1. Tổng số cách lấy 3 viên từ 12 viên: C(12,3) = 220.
2. Biến cố A: có ít nhất một bi đỏ. Số cách không có bi đỏ: C(7,3) = 35, nên n(A) = 220 - 35 = 185.
3. Biến cố B: đủ ba màu, tức 1 đỏ, 1 xanh, 1 vàng: 5*4*3 = 60 cách. Mọi cách này đều có bi đỏ nên B nằm trong A, n(A và B) = 60.
4. P(B|A) = n(A và B)/n(A) = 60/185 = 12/37.

### Uncertainty

low: Phép đếm đơn giản và đã đối chiếu bằng hai cách.
