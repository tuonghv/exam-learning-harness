# Expected Output

## Question 1

Final answer: B
Correct answer: B. 12

### Solution

1. Điều kiện lặp: i < 10; mỗi vòng s += i rồi i += 3.
2. Vòng 1: i=1 -> s=1, i=4. Vòng 2: i=4 -> s=5, i=7. Vòng 3: i=7 -> s=12, i=10.
3. i = 10 không thỏa i < 10 nên dừng; s = 1 + 4 + 7 = 12.

### Explanation

- A. 22: cộng thêm i = 10, tức coi điều kiện là i <= 10 (lỗi lệch một biên) - sai.
- B. 12: đúng, chỉ cộng các giá trị i = 1, 4, 7.
- C. 5: dừng sớm sau hai vòng (đếm thiếu một lần lặp) - sai.
- D. 10: đây là giá trị của i sau vòng lặp, không phải s - sai.

### Verification

- Check: chạy mô phỏng cho s = 12, i = 10 sau vòng lặp. Pass
- Check: số lần lặp = ceil((10-1)/3) = 3 và 1+4+7 = 12 (cấp số cộng: 3*(1+7)/2). Pass
- Edge case: vòng lặp dừng khi i = 10 (không còn i < 10), nên i = 10 không được cộng vào s. Pass
- Final answer: B
- Status: Verified

### Grading

- 1 point: option B. 0 points: any other option.
