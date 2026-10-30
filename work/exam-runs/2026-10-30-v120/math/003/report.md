# Exam report: Mathematics

- Exam: Mathematics, Grade 12, High School Graduation, task Multiple Choice, mode Solve
- Run: claude-p (sonnet), 2 call(s), cost $0.0329
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
| computed | unknown | no | arithmetic only: node not allowed: Call |
| ai_review | pass | no | reviewer: agree |
| key_match | pass | yes | matches the key |

### Explanation

A. 8: đúng, m thuộc {-5,...,2} gồm 8 số nguyên. B. 9: sai, nhầm khi tính cả m = 3 (delta' = 0, nghiệm kép, f' không đổi dấu nên không có cực trị). C. 7: sai, bỏ sót một giá trị (ví dụ m = -5 hoặc m = 2). D. 6: sai, đếm thiếu hai giá trị.

### Solution

1. Tập xác định: R. Đạo hàm f'(x) = 3x^2 - 6x + m.
2. Hàm bậc ba có hai điểm cực trị khi và chỉ khi f'(x) = 0 có hai nghiệm phân biệt (đổi dấu).
3. Điều kiện: delta' = 9 - 3m > 0, suy ra m < 3.
4. Với m nguyên thuộc [-5; 5]: m = -5, -4, -3, -2, -1, 0, 1, 2.
5. Biên m = 3: f'(x) = 3(x - 1)^2 >= 0, không đổi dấu nên không có cực trị, bị loại.
6. Vậy có 8 giá trị nguyên của m.

### Uncertainty

low: Điều kiện delta' > 0 chuẩn cho hàm bậc ba, biên m = 3 đã kiểm tra riêng.
