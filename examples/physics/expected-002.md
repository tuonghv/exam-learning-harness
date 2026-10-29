# Expected Output

## Question 1

Final answer: 2,67.10^5 Pa

### Solution

1. Given: V = const; T1 = 27 + 273 = 300 K; T2 = 127 + 273 = 400 K; p1 = 2,0.10^5 Pa.
2. Find: p2 (Pa).
3. Law: quá trình đẳng tích (Charles): p1/T1 = p2/T2, nhiệt độ phải tính bằng kelvin.
4. p2 = p1*T2/T1 = 2,0.10^5 * 400/300 = 2,667.10^5 Pa ≈ 2,67.10^5 Pa.

### Explanation

- Phải đổi °C sang K trước khi lập tỉ số. Nếu dùng °C trực tiếp sẽ ra 9,4.10^5 Pa (sai).
- Nhiệt độ tăng, thể tích không đổi nên áp suất tăng: p2 > p1.

### Verification

- Check: unit analysis: Pa * K/K = Pa. Pass
- Check: order of magnitude: tăng nhiệt độ tuyệt đối 4/3 lần nên p tăng 1,33 lần (2,0 -> 2,67). Pass
- Check: limiting case: nếu T2 = T1 thì p2 = p1; nếu T2 -> 0 K thì p2 -> 0. Pass
- Edge case: unit conversion Celsius -> Kelvin. Pass
- Final answer: 2,67.10^5 Pa
- Status: Verified

### Grading

- 1 point: 2,67.10^5 Pa (chấp nhận 2,7.10^5 Pa nếu đúng đơn vị). 0 points: wrong value or missing unit.
