# Exam report: Mathematics

- Exam: Mathematics, Grade 12, High School Graduation, task Multiple Choice, mode Solve
- Run: claude-p (sonnet), 2 call(s), cost $0.0323
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
| ai_review | pass | no | reviewer: agree |
| key_match | pass | yes | matches the key |

### QA findings

- ai_review / agree: f'(x) = 3x^2 - 6x + m có hai nghiệm phân biệt khi Delta' = 9 - 3m > 0, tức m < 3; m nguyên thuộc [-5; 2] gồm -5,-4,-3,-2,-1,0,1,2 là 8 giá trị, đáp án A đúng.

### Explanation

A. 8: đúng, có 8 số nguyên từ -5 đến 2. B. 9: sai, nhầm khi lấy cả m = 3, khi đó f'(x) = 3(x-1)^2 có nghiệm kép, không đổi dấu nên không có cực trị. C. 7: sai, bỏ sót một giá trị (ví dụ đếm thiếu m = 0 hoặc m = -5). D. 6: sai, đếm thiếu hai giá trị.

### Solution

1. Tập xác định: R. Đạo hàm: f'(x) = 3x^2 - 6x + m.
2. Hàm bậc ba có hai điểm cực trị khi và chỉ khi f'(x) = 0 có hai nghiệm phân biệt (đổi dấu).
3. Delta' = 9 - 3m > 0, suy ra m < 3.
4. Kết hợp m nguyên thuộc [-5; 5]: m thuộc {-5, -4, -3, -2, -1, 0, 1, 2}, có 8 giá trị.

### Uncertainty

low: Điều kiện Delta' > 0 chuẩn và biên m = 3 đã được kiểm tra riêng.
