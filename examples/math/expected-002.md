# Expected Output

## Question 1

Final answer: I = (e - 1)/2

### Solution

1. Hàm x·e^(x^2) liên tục trên [0; 1], không có điều kiện xác định đặc biệt.
2. Đặt u = x^2, du = 2x dx, nên x dx = du/2. Đổi cận: x = 0 thì u = 0; x = 1 thì u = 1.
3. I = (1/2) ∫ từ 0 đến 1 của e^u du = (1/2)[e^u] từ 0 đến 1 = (1/2)(e - 1).

### Explanation

- Đổi biến u = x^2 đưa tích phân về nguyên hàm cơ bản của e^u.
- Lỗi thường gặp: quên hệ số 1/2 (cho kết quả e - 1) hoặc quên đổi cận.

### Verification

- Check: nguyên hàm F(x) = (1/2)e^(x^2), F'(x) = x·e^(x^2) đúng. F(1) - F(0) = (e - 1)/2. Pass
- Check: tính số bằng quy tắc điểm giữa, 100000 đoạn, được 0.85914091 và (e - 1)/2 = 0.85914091. Pass
- Final answer: I = (e - 1)/2
- Status: Verified

### Grading

- 1 điểm: (e - 1)/2 (hoặc giá trị tương đương). 0 điểm: giá trị khác.
