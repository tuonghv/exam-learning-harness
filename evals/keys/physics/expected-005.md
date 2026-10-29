# Expected Output

## Question 1

Final answer: 1,8.10^-19 J

### Solution

1. Given: lambda = 0,30 μm = 3,0.10^-7 m; A = 3,0 eV = 3,0 * 1,6.10^-19 = 4,8.10^-19 J; h = 6,625.10^-34 J.s; c = 3.10^8 m/s.
2. Find: W_d,max (J).
3. Law (Einstein): hc/lambda = A + W_d,max.
4. hc/lambda = 6,625.10^-34 * 3.10^8 / 3,0.10^-7 = 6,625.10^-19 J (≈ 4,14 eV).
5. W_d,max = 6,625.10^-19 - 4,8.10^-19 = 1,825.10^-19 J ≈ 1,8.10^-19 J.

### Explanation

- Phải đổi μm sang m và eV sang J trước khi trừ. Nếu trừ 3,0 trực tiếp với 6,625.10^-19 J sẽ sai cỡ độ lớn.
- Photon (4,14 eV) lớn hơn công thoát (3,0 eV) nên hiện tượng quang điện xảy ra, W_d,max > 0.

### Verification

- Check: unit analysis: J.s * m/s / m = J. Pass
- Check: order of magnitude: năng lượng photon tử ngoại cỡ vài eV, tức cỡ 10^-19 J. Pass
- Check: limiting case: nếu lambda = hc/A = 4,1.10^-7 m (0,41 μm) thì W_d = 0; lambda = 0,30 μm nhỏ hơn nên W_d > 0. Pass
- Edge case: unit conversion μm -> m and eV -> J. Pass
- Final answer: 1,8.10^-19 J
- Status: Verified

### Grading

- 1 point: 1,8.10^-19 J (chấp nhận 1,14 eV hoặc 1,83.10^-19 J). 0 points: wrong value or missing unit.
