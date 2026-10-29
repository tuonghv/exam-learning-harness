# Expected Output

## Question 1

Final answer: A
Correct answer: A. 0,40 s (T = 0,397 s, làm tròn 2 chữ số có nghĩa)

### Solution

1. Given: m = 200 g = 0,200 kg (đổi g sang kg); k = 50 N/m.
2. Find: chu kì T (s).
3. Law: T = 2*pi*sqrt(m/k).
4. T = 2*pi*sqrt(0,200/50) = 2*pi*0,0632 = 0,397 s ≈ 0,40 s.

### Explanation

- A. 0,40 s: đúng, đổi m = 0,2 kg rồi dùng T = 2*pi*sqrt(m/k).
- B. 12,6 s: quên đổi 200 g ra kg (dùng m = 200) - sai.
- C. 2,5 s: đây là tần số f = 2,5 Hz, không phải chu kì (nhầm đơn vị Hz với s) - sai.
- D. 0,063 s: quên nhân 2*pi - sai.

### Verification

- Check: unit analysis: sqrt(kg / (N/m)) = sqrt(kg / (kg/s^2)) = s. Pass
- Check: order of magnitude: vật nhẹ, lò xo khá cứng nên T cỡ vài phần mười giây. Pass
- Check: limiting case: m tăng thì T tăng, k tăng thì T giảm; f = 1/T = 2,52 Hz nhất quán. Pass
- Edge case: unit conversion g -> kg (0,200 kg). Pass
- Final answer: A
- Status: Verified

### Grading

- 1 point: option A. 0 points: any other option.
