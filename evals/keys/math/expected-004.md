# Expected Output

## Question 1

Final answer: 37/42

### Solution

1. Không gian mẫu: lấy 3 viên từ 9 viên, |Ω| = C(9,3) = 84.
2. Biến cố đối: cả 3 viên đều đỏ, số cách C(5,3) = 10.
3. P(ít nhất một xanh) = 1 - 10/84 = 74/84 = 37/42.

### Explanation

- Dùng biến cố đối nhanh hơn cộng ba trường hợp (1, 2, 3 viên xanh).
- Lỗi thường gặp: quên rút gọn 74/84, hoặc dùng thứ tự (chỉnh hợp) thay cho tổ hợp.

### Verification

- Check: cộng trực tiếp: [C(4,1)·C(5,2) + C(4,2)·C(5,1) + C(4,3)] / 84 = (40 + 30 + 4)/84 = 74/84 = 37/42. Pass
- Final answer: 37/42
- Status: Verified

### Grading

- 1 điểm: 37/42 (hoặc giá trị tương đương). 0 điểm: giá trị khác.
