# Expected Output

## Question 1

Final answer: C
Correct answer: C. 90

### Solution

1. Đánh số bit từ phải sang trái (0..6): 1011010 -> bit6=1, bit5=0, bit4=1, bit3=1, bit2=0, bit1=1, bit0=0.
2. Cộng các trọng số 2^k của bit 1: 2^6 + 2^4 + 2^3 + 2^1.
3. 64 + 16 + 8 + 2 = 90.

### Explanation

- A. 45: đọc ngược dãy bit (0101101) hoặc chia đôi nhầm - sai.
- B. 180: dịch trái một bit (1011010 -> 10110100), tức nhân đôi giá trị - sai.
- C. 90: đúng, tổng các trọng số của bit 1.
- D. 89: nhầm với công thức 2^n - 1 hoặc trừ 1 vô cớ - sai.

### Verification

- Check: đổi ngược 90 -> nhị phân: 90 = 64+16+8+2 = 1011010. Pass
- Check: số 7 bit có bit cao nhất là 1 nên giá trị nằm trong [64, 127]; 90 thỏa. Pass
- Check: bit cuối là 0 nên số chẵn; 90 chẵn. Pass
- Edge case: thứ tự bit (bit phải nhất có trọng số 2^0), không đọc ngược. Pass
- Final answer: C
- Status: Verified

### Grading

- 1 point: option C. 0 points: any other option.
