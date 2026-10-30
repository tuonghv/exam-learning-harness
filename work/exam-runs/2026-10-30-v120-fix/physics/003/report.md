# Exam report: Physics

- Exam: Physics, Grade 12, High School Graduation, task Multiple Choice, mode Solve
- Run: claude-p (sonnet), 2 call(s), cost $0.0552
- Totals: PASS 0, FAIL 1, UNCERTAIN 0, unresolved 1
- Points: 1 / 1

## Question 1

- Answer: B
- Verdict: **FAIL**
- Reason: check_failed: quote
- Evidence: key match
- Score: 1 / 1 (official_key)

| Check | Result | Independent | Detail |
| --- | --- | --- | --- |
| format | pass | no | single letter A-D |
| computed | unknown | no | arithmetic only: node not allowed: Call |
| quote | pass | no | verbatim in passage/question: u = 100*sqrt(2)*cos(100*pi*t) (V) |
| quote | fail | no | verbatim in passage/question: R = 30 ohm, L = 0,4/pi H, C = 1,25.10^-4/pi F |
| key_match | pass | yes | matches the key |

### QA findings

- deterministic / quote: verbatim in passage/question: R = 30 ohm, L = 0,4/pi H, C = 1,25.10^-4/pi F
- deterministic / malformed_output: no valid JSON object found

### Explanation

B đúng: ZC = 80 ohm lớn hơn ZL = 40 ohm nên tan(phi) = -4/3, phi = -0,93 rad. A sai: đúng độ lớn nhưng sai dấu (dấu + ứng với mạch có tính cảm kháng, ZL > ZC). C sai: -0,64 rad là arctan(3/4), do lấy tỉ số R/(ZC - ZL) thay vì (ZL - ZC)/R. D sai: vừa sai dấu vừa nhầm tỉ số như C.

### Solution

1. Given: u = 100*sqrt(2)*cos(100*pi*t) V, nên omega = 100*pi rad/s; R = 30 ohm; L = 0,4/pi H; C = 1,25.10^-4/pi F. Find: phi = phi_u - phi_i (rad).
2. Cảm kháng: ZL = omega*L = 100*pi*0,4/pi = 40 ohm.
3. Dung kháng: ZC = 1/(omega*C) = 1/(100*pi*1,25.10^-4/pi) = 80 ohm.
4. Định luật: tan(phi) = (ZL - ZC)/R = (40 - 80)/30 = -4/3.
5. phi = arctan(-4/3) = -0,927 rad, làm tròn -0,93 rad (ZC > ZL nên mạch có tính dung kháng, u trễ pha so với i).

### Uncertainty

low: Phép tính trực tiếp, đáp án khớp đúng một lựa chọn.
