# Expected Output

## Question 1

Final answer: 3
Correct answer: 3 (ba dòng)

### Solution

1. Given: bảng 7 dòng, cột diem có hai giá trị NULL (ma 3 và 6).
2. Find: số dòng thỏa diem < 5.
3. WHERE giữ dòng có điều kiện đúng; so sánh với NULL cho kết quả không xác định (UNKNOWN) nên dòng bị loại.
4. Các dòng thỏa: An (4.5), Dung (3.0), Em (4.5) -> COUNT(*) = 3.

### Explanation

- Kết quả 3: đếm cả hai dòng trùng điểm 4.5 (COUNT(*) không loại trùng) và bỏ hai dòng NULL.
- Đáp án 5 là sai: coi NULL như nhỏ hơn 5 hoặc như 0.
- Đáp án 2 là sai: dùng COUNT(DISTINCT diem), bỏ trùng điểm 4.5.
- Đáp án 7 là sai: bỏ qua mệnh đề WHERE.

### Verification

- Check: chạy sqlite3 với dữ liệu trên: 3; số dòng diem >= 5 là 2; 3 + 2 = 5 = 7 - 2 dòng NULL. Pass
- Check: COUNT(diem) = 5 dòng không NULL, trong đó 2 dòng >= 5 nên còn 3. Pass
- Edge case: NULL không thỏa diem < 5 và cũng không thỏa diem >= 5; trùng điểm vẫn đếm. Pass
- Final answer: 3
- Status: Verified

### Grading

- 1 point: 3. 0 points: any other value.
