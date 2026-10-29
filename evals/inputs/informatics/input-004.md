# Exam Input

Subject: Tin hoc
Level: Grade 12
Exam type: High School Graduation
Task: Short Answer
Mode: Solve
Skill: Databases - SQL query result with NULL
Language: vi

## Instructions

Trả lời ngắn gọn kèm đơn vị (nếu có) và giải thích cách tính.

## Question 1

Bảng HOCSINH có dữ liệu như sau (NULL nghĩa là chưa có điểm):

| ma | ten  | lop | diem |
|----|------|-----|------|
| 1  | An   | 12A | 4.5  |
| 2  | Binh | 12A | 7.0  |
| 3  | Chi  | 12B | NULL |
| 4  | Dung | 12B | 3.0  |
| 5  | Em   | 12A | 4.5  |
| 6  | Ga   | 12C | NULL |
| 7  | Ha   | 12C | 5.0  |

Câu lệnh `SELECT COUNT(*) FROM HOCSINH WHERE diem < 5;` trả về giá trị bao nhiêu?
