# Expected Output

## Question 1

Final answer: 62 địa chỉ host
Correct answer: 62 (expr: 2**(32-26)-2 = 62)

### Solution

1. Given: địa chỉ 192.168.10.0/26 -> độ dài tiền tố 26 bit, tổng 32 bit.
2. Find: số địa chỉ host dùng được.
3. Số bit host = 32 - 26 = 6; tổng địa chỉ = 2^6 = 64.
4. Trừ địa chỉ mạng (192.168.10.0) và quảng bá (192.168.10.63): 64 - 2 = 62.

### Explanation

- Kết quả 62 địa chỉ host (192.168.10.1 đến 192.168.10.62).
- Đáp án 64 sai: quên trừ địa chỉ mạng và địa chỉ quảng bá.
- Đáp án 30 sai: dùng nhầm /27 (5 bit host).
- Đáp án 26 sai: lấy nhầm độ dài tiền tố làm số host.

### Verification

- Check: recompute: 2**(32-26)-2 = 62. Pass
- Check: dải host 192.168.10.1..62 có 62 địa chỉ; broadcast = 0 + 64 - 1 = 63. Pass
- Check: order of magnitude: /24 có 254 host, mỗi bit tiền tố thêm chia đôi: 254 -> 126 -> 62 (/26). Pass
- Edge case: trừ 2 địa chỉ đặc biệt (mạng, quảng bá). Pass
- Final answer: 62 địa chỉ host
- Status: Verified

### Grading

- 1 point: 62 (host). 0 points: any other value.
