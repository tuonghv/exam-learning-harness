# Exam report: Physics

- Exam: Physics, Grade 12, High School Graduation, task Multiple Choice, mode Solve
- Run: claude-p (sonnet), 2 call(s), cost $0.0384
- Totals: PASS 1, FAIL 0, UNCERTAIN 0, unresolved 0
- Points: 1 / 1

## Question 1

- Answer: B
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

### QA findings

- ai_review / agree: omega=100*pi, ZL=40 ohm, ZC=1/(100*pi*1,25.10^-4/pi)=80 ohm, tan(phi)=(40-80)/30=-4/3, phi=-0,927 rad ≈ -0,93 rad, khớp đáp án B.

### Explanation

B đúng: ZC > ZL nên mạch có tính dung kháng, u trễ pha hơn i, phi = -0,927 rad ≈ -0,93 rad. A (+0,93 rad) sai dấu: nó ứng với mạch có tính cảm kháng (ZL > ZC), tức nhầm phi = phi_i - phi_u hoặc đổi chỗ ZL và ZC. C (-0,64 rad) sai độ lớn: 0,64 rad ứng với tan = 0,75 = 30/40, tức dùng R/(ZC - ZL) hoặc nhầm tử và mẫu. D (+0,64 rad) sai cả dấu lẫn độ lớn.

### Solution

1. Given: u = 100*sqrt(2)*cos(100*pi*t) V nên omega = 100*pi rad/s; R = 30 ohm; L = 0,4/pi H; C = 1,25.10^-4/pi F. Find: phi = phi_u - phi_i (rad).
2. Cảm kháng ZL = omega*L = 100*pi*0,4/pi = 40 ohm. Dung kháng ZC = 1/(omega*C) = 1/(100*pi*1,25.10^-4/pi) = 80 ohm.
3. Law: tan(phi) = (ZL - ZC)/R = (40 - 80)/30 = -4/3, nên phi = arctan(-4/3) = -0,927 rad, làm tròn -0,93 rad (phi < 0: điện áp trễ pha so với dòng điện, mạch có tính dung kháng).

### Uncertainty

low: Phép tính trực tiếp, dấu của phi xác định rõ do ZC > ZL.
