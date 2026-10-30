# Exam report: Physics

- Exam: Physics, Grade 12, High School Graduation, task Short Answer, mode Solve
- Run: claude-p (sonnet), 2 call(s), cost $0.0347
- Totals: PASS 1, FAIL 0, UNCERTAIN 0, unresolved 0
- Points: 1 / 1

## Question 1

- Answer: 9 điểm
- Verdict: **PASS**
- Reason: independent check passed and reviewer agrees
- Evidence: key match
- Score: 1 / 1 (official_key)

| Check | Result | Independent | Detail |
| --- | --- | --- | --- |
| format | pass | no | answer holds a number |
| computed | unknown | no | arithmetic only: node not allowed: Call |
| quote | pass | no | verbatim in passage/question: cách nhau 10 cm, dao động cùng pha |
| quote | pass | no | verbatim in passage/question: tần số 15 Hz |
| quote | pass | no | verbatim in passage/question: Tốc độ truyền sóng trên mặt nước là 30 cm/s |
| quote | pass | no | verbatim in passage/question: không tính hai nguồn A và B |
| ai_review | pass | no | reviewer: agree |
| key_match | pass | yes | matches the key |

### Explanation

Hai nguồn cùng pha nên cực đại thỏa d1 - d2 = k*lambda, trung điểm AB ứng với k = 0. Do k = +5 và k = -5 ứng với đúng vị trí hai nguồn A và B (bị loại theo đề bài) nên chỉ lấy |k| <= 4, được 9 điểm. Nếu dùng công thức bao gồm cả biên thì sẽ được 11 điểm (sai vì đề không tính A, B). Nếu dùng công thức của hai nguồn ngược pha hoặc lấy 2*[AB/lambda] thì sẽ ra 10 điểm (sai).

### Solution

1. Given: AB = 10 cm; f = 15 Hz; v = 30 cm/s; hai nguồn cùng pha. Find: số điểm cực đại trên AB (không tính A, B).
2. Bước sóng: lambda = v/f = 30/15 = 2 cm.
3. Điều kiện cực đại (cùng pha): d1 - d2 = k*lambda, với -AB < d1 - d2 < AB (không tính hai nguồn).
4. Suy ra -AB/lambda < k < AB/lambda, tức -5 < k < 5.
5. k nguyên: k = -4, -3, ..., 3, 4 nên có 9 giá trị.

### Uncertainty

low: Bài chuẩn, AB/lambda = 5 nguyên nên chỉ cần loại hai điểm biên theo đề.
