# Exam report: Mathematics

- Exam: Mathematics, Grade 12, University Entrance (DGNL), task Multiple Choice, mode Solve
- Run: claude-p (sonnet), 2 call(s), cost $0.0425
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
| ai_review | pass | no | reviewer: agree |
| key_match | pass | yes | matches the key |

### Explanation

A. 12: sai, thiếu cách, ví dụ chỉ đếm 6 cách cho mỗi trường hợp E ở vị trí 2 hoặc 4. B. 16: đúng, bằng 8 + 8 + 0. C. 20: sai, dư cách, chẳng hạn tính cả trường hợp E ở vị trí 3 mà C, D kề nhau. D. 24: sai, dư cách vì không loại hết các trường hợp vi phạm điều kiện C, D không kề nhau hoặc E ở vị trí giữa.

### Solution

1. E đứng ở vị trí 2, 3 hoặc 4. Xét từng trường hợp, rồi xếp A, B (đứng cạnh nhau) và C, D (không đứng cạnh nhau) vào 4 vị trí còn lại.
2. E ở vị trí 2: các vị trí còn lại là 1, 3, 4, 5. Hai vị trí kề nhau chỉ có (3,4) và (4,5). A, B chiếm (3,4) hoặc (4,5), mỗi cách có 2 hoán đổi, nên có 4 cách xếp A, B.
3. Khi A, B ở (3,4), C, D ở vị trí 1 và 5 (không kề nhau). Khi A, B ở (4,5), C, D ở vị trí 1 và 3 (không kề nhau). Cả hai trường hợp đều thỏa mãn, mỗi trường hợp C, D có 2 cách: 4 x 2 = 8 cách.
4. E ở vị trí 4: đối xứng với E ở vị trí 2, có 8 cách.
5. E ở vị trí 3: các vị trí còn lại là 1, 2, 4, 5. A, B phải chiếm (1,2) hoặc (4,5), khi đó C, D chiếm cặp còn lại là hai vị trí kề nhau, vi phạm điều kiện. Có 0 cách.
6. Tổng: 8 + 8 + 0 = 16 cách.

### Uncertainty

low: Số trường hợp ít, đếm trực tiếp và có kiểm tra bằng đối xứng.
