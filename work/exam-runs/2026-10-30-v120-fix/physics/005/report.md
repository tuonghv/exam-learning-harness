# Exam report: Physics

- Exam: Physics, Grade 12, High School Graduation, task Short Answer, mode Solve
- Run: claude-p (sonnet), 2 call(s), cost $0.0386
- Totals: PASS 1, FAIL 0, UNCERTAIN 0, unresolved 0
- Points: 1 / 1

## Question 1

- Answer: 1,8.10^-19 J (làm tròn đến 2 chữ số có nghĩa)
- Verdict: **PASS**
- Reason: independent check passed and reviewer agrees
- Evidence: code oracle
- Score: 1 / 1 (official_key)

| Check | Result | Independent | Detail |
| --- | --- | --- | --- |
| format | pass | no | answer holds a number |
| computed | pass | yes | arithmetic only: 6.625e-34*3e8/0.30e-6 - 3.0*1.6e-19 = 1.825e-19, answer 1.8e-19 |
| quote | pass | no | verbatim in passage/question: Chiếu bức xạ có bước sóng 0,30 μm vào bề mặt một tấm kim loại có công thoát elec |
| ai_review | pass | no | reviewer: agree |
| key_match | pass | yes | matches the key |

### Explanation

Năng lượng photon 6,625.10^-19 J lớn hơn công thoát 4,8.10^-19 J nên có hiện tượng quang điện. Phần năng lượng dư là động năng ban đầu cực đại của electron: 1,825.10^-19 J, làm tròn 1,8.10^-19 J. Cần đổi um sang m và eV sang J trước khi tính.

### Solution

1. Given: lambda = 0,30 um = 0,30.10^-6 m; A = 3,0 eV = 3,0.1,6.10^-19 = 4,8.10^-19 J; h = 6,625.10^-34 J.s; c = 3.10^8 m/s. Find: W_d0max (J).
2. Law (Einstein): h*c/lambda = A + W_d0max, nên W_d0max = h*c/lambda - A.
3. h*c/lambda = 6,625.10^-34 * 3.10^8 / (0,30.10^-6) = 6,625.10^-19 J.
4. W_d0max = 6,625.10^-19 - 4,8.10^-19 = 1,825.10^-19 J, làm tròn thành 1,8.10^-19 J.

### Uncertainty

low: Áp dụng trực tiếp công thức Einstein với dữ kiện đầy đủ, phép tính đơn giản.
