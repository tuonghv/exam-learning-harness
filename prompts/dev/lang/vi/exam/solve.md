Nhiệm vụ: giải tệp đề thi dưới đây.

Đầu vào: văn bản tệp đề thi (định dạng của examples/FORMAT.md: các dòng tiêu đề, Instructions, tùy chọn
Passage, rồi các khối `## Question N`) và `Language: vi|en` cho phần giải thích của bạn.

Quy tắc
1. Đọc toàn bộ tệp trước. Giải mọi câu hỏi.
2. Giải thích bằng ngôn ngữ ghi trong giá trị `Language:`. Các mục tiếng Anh giữ nguyên tiếng Anh. Không dịch câu hỏi.
3. `answer` theo loại: trắc nghiệm = một chữ cái A-D; sắp xếp câu = các chữ cái nối bằng `-`
   (`c-a-d-b-e`); tính toán = giá trị, đơn vị và cách làm tròn đã dùng (`2.5 m/s^2`); trả lời ngắn = giá trị
   hoặc cụm từ chính xác; Ngữ văn hoặc bài tự luận khác = `Open`.
4. `checks` = ít nhất một cách khác để xác nhận đáp án (thay ngược lại, phân tích đơn vị, trường hợp giới
   hạn, trích dẫn). Với bài tính toán, cũng ghi `expr`: biểu thức số cuối cùng dưới dạng phép tính Python
   thuần, để mã có thể tính lại.

Output
{"schema_version":"1.0","questions":[{"id":"1","type":"multiple_choice","answer":"A",
"answer_status":"answered","solution":["step 1","step 2"],"explanation":"why, and why each other option is wrong",
"checks":["check text"],"expr":null,"evidence":["exact quote or null"],"uncertainty":{"level":"low","reason":""},
"reasoning_status":"not_independently_verified","issues":[]}],"input_issues":[]}

`answer_status` là answered | uncertain | unanswerable.
