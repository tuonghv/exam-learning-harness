# Exam report: Mathematics

- Exam: Mathematics, Grade 12, University Entrance (DGNL), task Multiple Choice, mode Solve
- Run: claude-p (sonnet), 2 call(s), cost $0.0434
- Totals: PASS 1, FAIL 0, UNCERTAIN 0, unresolved 0
- Points: 1 / 1

## Question 1

- Answer: C
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

A. 1000: sai, không ứng với d nào (tích chỉ có thể là 231 hoặc -504). B. -504: là tích ở trường hợp d = -11, nhưng đây là giá trị nhỏ hơn, không phải lớn nhất. C. 231: đúng, là tích ở trường hợp d = 4 và lớn hơn -504. D. 252: sai, không ứng với nghiệm nào của phương trình.

### Solution

1. Gọi ba số là 7-d, 7, 7+d (gọi số giữa là a thì 3a = 21 nên a = 7). Không có điều kiện xác định nào khác, d là số thực bất kỳ.
2. Sau khi cộng 2, 3, 9: 9-d, 10, 16+d lập thành cấp số nhân nên (9-d)(16+d) = 10^2 = 100.
3. Khai triển: 144 - 7d - d^2 = 100, suy ra d^2 + 7d - 44 = 0, nên d = 4 hoặc d = -11 (cả hai đều nhận, không có nghiệm ngoại lai).
4. d = 4: ba số 3, 7, 11, tích = 231. d = -11: ba số 18, 7, -4, tích = -504.
5. Tích lớn nhất là 231.

### Uncertainty

low: Hai nghiệm d đều được kiểm tra trực tiếp và chỉ có hai giá trị tích để so sánh.
