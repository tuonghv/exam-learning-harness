# Expected Output

## Question 1

Final answer: 9 (cực đại)

### Solution

1. Given: AB = 10 cm = 0,10 m; f = 15 Hz; v = 30 cm/s = 0,30 m/s; hai nguồn cùng pha.
2. Find: số điểm cực đại trên đoạn AB, không tính A và B.
3. Law: lambda = v/f = 0,30/15 = 0,020 m = 2 cm.
4. Hai nguồn cùng pha: cực đại khi d2 - d1 = k*lambda, với -AB < d2 - d1 < AB (hai đầu mút bị loại), nên -AB/lambda < k < AB/lambda.
5. AB/lambda = 10/2 = 5, nên -5 < k < 5 (bất đẳng thức chặt) và k nguyên: k = -4, ..., 4.
6. Có 9 giá trị k nên có 9 cực đại.

### Explanation

- k = ±5 ứng với d2 - d1 = ±AB, chỉ xảy ra tại chính nguồn A, B nên bị loại theo đề. Đếm cả hai sẽ ra 11 (sai).
- Đơn vị cm và m phải thống nhất: lambda = 2 cm cùng đơn vị với AB = 10 cm.

### Verification

- Check: unit analysis: lambda = (m/s)/Hz = m; AB/lambda không thứ nguyên. Pass
- Check: order of magnitude: khoảng cách giữa hai cực đại liên tiếp là lambda/2 = 1 cm, nên trên 10 cm có khoảng 9 điểm. Pass
- Check: limiting case: AB/lambda = 5 đúng số nguyên nên biên k = ±5 bị loại; số cực đại là 2*5 - 1 = 9. Pass
- Edge case: unit conversion cm <-> m; boundary k = ±5 excluded. Pass
- Final answer: 9 (cực đại)
- Status: Verified

### Grading

- 1 point: 9. 0 points: any other value (11 and 10 are the typical errors).
