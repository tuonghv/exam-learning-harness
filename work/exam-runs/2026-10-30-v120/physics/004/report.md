# Exam report: Physics

- Exam: Physics, Grade 12, High School Graduation, task Short Answer, mode Solve
- Run: claude-p (sonnet), 2 call(s), cost $0.0344
- Totals: PASS 0, FAIL 1, UNCERTAIN 0, unresolved 1
- Points: 0 / 1

## Question 1

- Answer: 9 điểm
- Verdict: **FAIL**
- Reason: differs_from_key
- Evidence: code oracle
- Score: 0 / 1 (official_key)

| Check | Result | Independent | Detail |
| --- | --- | --- | --- |
| format | pass | no | answer holds a number |
| computed | pass | yes | arithmetic only: 2*(10/(30/15) - 1) + 1 = 9, answer 9 |
| quote | pass | no | verbatim in passage/question: cách nhau 10 cm, dao động cùng pha |
| quote | pass | no | verbatim in passage/question: tần số 15 Hz |
| quote | pass | no | verbatim in passage/question: Tốc độ truyền sóng trên mặt nước là 30 cm/s |
| quote | pass | no | verbatim in passage/question: không tính hai nguồn A và B |
| ai_review | pass | no | reviewer: agree |

### QA findings

- score / differs_from_key: answer differs from the key

### Explanation

Hai nguồn cùng pha nên cực đại ứng với hiệu đường đi bằng số nguyên lần bước sóng. AB/lambda = 5 là số nguyên, nên k = +5 và k = -5 ứng với đúng vị trí hai nguồn A và B, bị loại theo yêu cầu đề. Nếu tính cả hai nguồn sẽ được 11 điểm (sai vì đề nói không tính). Nếu dùng công thức 2*floor(AB/lambda)+1 mà không loại biên cũng ra 11 (sai).

### Solution

1. Given: AB = 10 cm; f = 15 Hz; v = 30 cm/s; hai nguồn cùng pha. Find: số điểm cực đại trên đoạn AB (không tính A, B).
2. Bước sóng: lambda = v/f = 30/15 = 2 cm.
3. Điều kiện cực đại với hai nguồn cùng pha: d2 - d1 = k*lambda, với -AB < d2 - d1 < AB (không tính hai nguồn nên bỏ dấu bằng).
4. Suy ra -AB/lambda < k < AB/lambda, tức -5 < k < 5.
5. k nguyên nên k = -4, -3, ..., 4, tổng cộng 9 giá trị, tức 9 điểm.

### Uncertainty

low: Bài chuẩn; chỉ cần chú ý loại hai nguồn khi AB/lambda là số nguyên.
