# Expected Output

## Question 1

Final answer: C
Correct answer: C. a = 1, b = 1, c = 0

### Solution

1. Điều kiện: a, b, c thuộc {0, 1}; thứ tự ưu tiên NOT > AND > OR, dấu ngoặc tính trước.
2. Với a = 1, b = 1, c = 0: (a OR b) = 1; (a AND c) = 0 nên NOT(a AND c) = 1.
3. F = 1 AND 1 = 1.

### Explanation

- A. a=1, b=0, c=1: (a OR b)=1 nhưng a AND c = 1 nên NOT = 0, F = 0 - sai.
- B. a=0, b=0, c=1: a OR b = 0 nên F = 0 - sai.
- C. a=1, b=1, c=0: F = 1 - đúng.
- D. a=1, b=1, c=1: a AND c = 1 nên NOT = 0, F = 0 - sai.

### Verification

- Check: lập bảng chân trị 8 tổ hợp, F = 1 chỉ với (0,1,0), (0,1,1), (1,0,0), (1,1,0); trong các phương án chỉ có C nằm trong tập này. Pass
- Check: F = 1 đòi hỏi a OR b = 1 và không đồng thời a = c = 1; A, D vi phạm vế sau, B vi phạm vế đầu. Pass
- Edge case: phủ định áp dụng cho cả (a AND c), không chỉ cho a. Pass
- Final answer: C
- Status: Verified

### Grading

- 1 point: option C. 0 points: any other option.
