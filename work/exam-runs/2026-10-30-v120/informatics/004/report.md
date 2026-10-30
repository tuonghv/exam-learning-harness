# Exam report: Tin hoc

- Exam: Tin hoc, Grade 12, High School Graduation, task Short Answer, mode Solve
- Run: claude-p (sonnet), 3 call(s), cost $0.0532
- Totals: PASS 1, FAIL 0, UNCERTAIN 0, unresolved 0
- Points: 1 / 1

## Question 1

- Answer: 3
- Verdict: **PASS**
- Reason: independent check passed and reviewer agrees
- Evidence: code oracle
- Score: 1 / 1 (official_key)

| Check | Result | Independent | Detail |
| --- | --- | --- | --- |
| computed | pass | yes | arithmetic only: 1 + 1 + 1 = 3, answer 3 |
| quote | pass | no | verbatim in passage/question: SELECT COUNT(*) FROM HOCSINH WHERE diem < 5; |
| ai_review | pass | no | reviewer: agree |
| key_match | pass | yes | matches the key |

### Explanation

Kết quả là 3 dòng (ma = 1, 4, 5). Đáp án 4 sai vì đã tính nhầm một dòng NULL (Chi hoặc Ga) vào kết quả, trong khi so sánh với NULL không bao giờ cho TRUE. Ha có điểm 5.0 không nhỏ hơn 5 nên cũng không được tính. Nếu đếm cả hai dòng NULL thì sẽ ra 5, cũng sai.

### Solution

1. Điều kiện WHERE diem < 5 chỉ giữ các dòng mà biểu thức cho kết quả TRUE.
2. Duyệt bảng: An (4.5) đạt, Binh (7.0) không, Chi (NULL) không, Dung (3.0) đạt, Em (4.5) đạt, Ga (NULL) không, Ha (5.0) không.
3. Với NULL, phép so sánh NULL < 5 cho kết quả UNKNOWN nên dòng bị loại. COUNT(*) đếm các dòng còn lại: An, Dung, Em = 3.

### Uncertainty

low: Quy tắc logic ba giá trị của SQL với NULL rõ ràng và chỉ có 7 dòng để đếm.
