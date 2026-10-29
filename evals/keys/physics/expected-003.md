# Expected Output

## Question 1

Final answer: B
Correct answer: B. -0,93 rad (φ = -0,927 rad)

### Solution

1. Given: omega = 100*pi rad/s; R = 30 ohm; L = 0,4/pi H; C = 1,25.10^-4/pi F.
2. Find: φ = φu - φi (rad).
3. Law: tan φ = (Z_L - Z_C)/R với Z_L = omega*L, Z_C = 1/(omega*C).
4. Z_L = 100*pi*0,4/pi = 40 ohm; Z_C = 1/(100*pi*1,25.10^-4/pi) = 80 ohm.
5. tan φ = (40 - 80)/30 = -4/3, nên φ = arctan(-4/3) = -0,927 rad ≈ -0,93 rad (dấu âm: mạch có tính dung kháng, u trễ pha so với i).

### Explanation

- A. +0,93 rad: đúng độ lớn nhưng sai dấu (lấy Z_C - Z_L) - sai.
- B. -0,93 rad: đúng, Z_C > Z_L nên u trễ pha so với i.
- C. -0,64 rad: dùng tan φ = R/(Z_C - Z_L) = 3/4 (nhầm tỉ số) - sai.
- D. +0,64 rad: nhầm cả tỉ số lẫn dấu - sai.

### Verification

- Check: unit analysis: Z_L, Z_C, R cùng đơn vị ohm, tỉ số không thứ nguyên, φ tính bằng rad. Pass
- Check: order of magnitude: |φ| < pi/2 = 1,57 rad và 53 độ = 0,93 rad. Pass
- Check: limiting case: nếu Z_L = Z_C thì φ = 0 (cộng hưởng); mạch có Z_C > Z_L nên φ < 0. Pass
- Edge case: sign/direction of φ (u trễ pha so với i). Pass
- Final answer: B
- Status: Verified

### Grading

- 1 point: option B. 0 points: any other option.
