# Exam report: Physics

- Exam: Physics, Grade 12, High School Graduation, task Short Answer, mode Solve
- Run: claude-p (sonnet), 2 call(s), cost $0.0474
- Totals: PASS 0, FAIL 1, UNCERTAIN 0, unresolved 1
- Points: 0 / 1

## Question 1

- Answer: ​1.8e-19 J (làm tròn đến 2 chữ số có nghĩa)
- Verdict: **FAIL**
- Reason: differs_from_key
- Evidence: Claude review only
- Score: 0 / 1 (official_key)

| Check | Result | Independent | Detail |
| --- | --- | --- | --- |
| format | pass | no | answer holds a number |
| computed | fail | yes | arithmetic only: 6.625e-34*3e8/0.30e-6 - 3.0*1.6e-19 = 1.825e-19, answer 1.8 |
| quote | pass | no | verbatim in passage/question: Chiếu bức xạ có bước sóng 0,30 μm vào bề mặt một tấm kim loại có công thoát elec |

### QA findings

- deterministic / computed: arithmetic only: 6.625e-34*3e8/0.30e-6 - 3.0*1.6e-19 = 1.825e-19, answer 1.8
- score / differs_from_key: answer differs from the key

### Explanation

Áp dụng phương trình Einstein về hiệu ứng quang điện: năng lượng photon bằng công thoát cộng động năng ban đầu cực đại. Năng lượng photon 6.625e-19 J lớn hơn công thoát 4.8e-19 J nên có hiện tượng quang điện và động năng dương. Đổi đơn vị: um sang m (nhân 1e-6) và eV sang J (nhân 1.6e-19).

### Solution

1. Given: lambda = 0.30 um = 0.30e-6 m; A = 3.0 eV = 3.0*1.6e-19 = 4.8e-19 J; h = 6.625e-34 J.s; c = 3e8 m/s.
2. Find: động năng ban đầu cực đại W0max (J).
3. Định luật: hc/lambda = A + W0max, suy ra W0max = hc/lambda - A.
4. Năng lượng photon: hc/lambda = 6.625e-34*3e8/0.30e-6 = 6.625e-19 J.
5. W0max = 6.625e-19 - 4.8e-19 = 1.825e-19 J, làm tròn 2 chữ số có nghĩa: 1.8e-19 J.

### Uncertainty

low: Bài áp dụng trực tiếp công thức Einstein, phép tính đơn giản.
