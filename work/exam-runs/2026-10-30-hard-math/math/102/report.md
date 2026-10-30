# Exam report: Mathematics

- Exam: Mathematics, Grade 12, University Entrance (DGNL), task Multiple Choice, mode Solve
- Run: claude-p (sonnet), 2 call(s), cost $0.0359
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
| computed | unknown | no | arithmetic only: answer has no number |
| ai_review | pass | no | reviewer: agree |
| key_match | pass | yes | matches the key |

### Explanation

B đúng: 12960 là số cách thỏa cả hai điều kiện. A (14400) sai vì chưa loại trường hợp An đứng đầu bên trái. C (11520) sai vì trừ quá nhiều. D (1440) sai vì chỉ là số cách An đứng đầu, đây là số cần loại bỏ chứ không phải đáp số.

### Solution

1. Xếp 5 nam trước: 5! = 120 cách, tạo 6 khoảng trống (2 đầu và 4 giữa).
2. Chọn 3 khoảng trống cho 3 nữ để không có hai nữ cạnh nhau: C(6,3) = 20, xếp 3 nữ: 3! = 6. Tổng không điều kiện An: 120*20*6 = 14400.
3. Trường hợp An đứng đầu hàng bên trái: xếp 4 nam còn lại 4! = 24 cách. Khoảng trống phía trước An không dùng được nên còn 5 khoảng trống, chọn C(5,3) = 10, xếp nữ 3! = 6. Số cách: 24*10*6 = 1440.
4. Đáp số: 14400 - 1440 = 12960.

### Uncertainty

low: Bài đếm bằng phương pháp xếp khoảng trống chuẩn, có kiểm tra bằng đếm trực tiếp.
