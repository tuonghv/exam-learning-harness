# Expected Output

## Question 1

Final answer: A
Correct answer: A. 8

### Solution

1. Hàm số xác định trên R. f'(x) = 3x^2 - 6x + m.
2. Hàm bậc ba có hai điểm cực trị khi và chỉ khi f'(x) = 0 có hai nghiệm phân biệt: Δ' = 9 - 3m > 0, tức m < 3.
3. Tại biên m = 3: f'(x) = 3(x - 1)^2 ≥ 0, nghiệm kép, f'(x) không đổi dấu nên không có cực trị; loại m = 3.
4. Các số nguyên m thuộc [-5; 5] với m < 3 là -5, -4, -3, -2, -1, 0, 1, 2: có 8 giá trị.

### Explanation

- A. 8: đúng, m ∈ {-5, ..., 2}.
- B. 9: sai, đếm cả m = 3 (nghiệm kép, không có cực trị).
- C. 7: sai, bỏ sót một giá trị biên, ví dụ bỏ m = -5 hoặc m = 2.
- D. 6: sai, nhầm điều kiện (ví dụ chỉ đếm m từ -3 đến 2).

### Verification

- Check: kiểm tra bằng chương trình, đếm m nguyên trong [-5; 5] có 36 - 12m > 0 được 8 giá trị. Pass
- Check: m = 2 cho f' = 3x^2 - 6x + 2 có Δ' = 3 > 0 (có cực trị); m = 3 cho Δ' = 0 (không có). Pass
- Final answer: A
- Status: Verified

### Grading

- 1 điểm: đáp án A. 0 điểm: đáp án khác.
