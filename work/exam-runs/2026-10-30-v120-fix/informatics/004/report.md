# Exam report: Tin hoc

- Exam: Tin hoc, Grade 12, High School Graduation, task Short Answer, mode Solve
- Run: claude-p (sonnet), 2 call(s), cost $0.0334
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

### QA findings

- ai_review / agree: Các dòng có diem < 5 là ma 1 (4.5), 4 (3.0), 5 (4.5); dòng NULL cho UNKNOWN bị loại và 5.0 < 5 là FALSE, nên COUNT(*) = 3.

### Explanation

Kết quả là 3 vì COUNT(*) đếm các dòng thỏa WHERE, và NULL < 5 cho UNKNOWN nên không được tính. Đáp án 5 sai vì tính nhầm cả 2 dòng NULL như thể thỏa điều kiện. Đáp án 4 sai vì chỉ tính thêm một dòng NULL hoặc tính nhầm điểm 5.0 (5.0 < 5 là FALSE). Đáp án 2 sai vì bỏ sót một trong hai học sinh có 4.5.

### Solution

1. Điều kiện WHERE diem < 5 chỉ giữ các dòng có kết quả TRUE; dòng có diem = NULL cho kết quả UNKNOWN nên bị loại.
2. Bảng theo dõi: ma1 (4.5) TRUE; ma2 (7.0) FALSE; ma3 (NULL) UNKNOWN; ma4 (3.0) TRUE; ma5 (4.5) TRUE; ma6 (NULL) UNKNOWN; ma7 (5.0) FALSE.
3. Các dòng thỏa: ma 1, 4, 5 nên COUNT(*) = 3.

### Uncertainty

low: Quy tắc logic ba trị của SQL với NULL là chuẩn và dữ liệu bảng nhỏ, rõ ràng.
