Task: transcribe the exam questions visible in the attached page image into JSON.

Rules
1. Transcribe only what is visible. Do not solve, explain or add anything. Do not invent text.
2. Keep the original language and wording. Write math in plain text (x^2, sqrt(x), a/b, pi).
3. One entry per question, in page order. `id` is the question number as printed.
4. Multiple choice: put the options under `options` with keys A, B, C, D. No options: `{}`.
5. Pictures, graphs or tables you cannot transcribe: describe the kind briefly under `figures`.
6. If part of a question is unreadable, transcribe the rest and set `"unreadable": true`.
7. A reading passage or shared instruction for several questions (e.g. "Questions 46-52: read the passage") goes in `context` of the FIRST question that uses it, copied in full; later ones leave `context` empty.
8. Options at the top of the page that continue a question begun on the previous page: output them as one entry with `"id":""`, `"text":""`, the options, and `"unreadable":true`. A question whose text is cut at the page bottom: transcribe what is visible.
9. A passage, table or shared instruction printed on this page whose questions all start on the next page (never a question itself; a question cut at the page bottom stays in `questions`): put it, in full, in the top-level `carry` (empty when none).
10. Never output an answer, a solution, a key or a hint.

Output (JSON only)
{"questions":[{"id":"1","text":"question text","options":{"A":"..","B":".."},"context":"","figures":[],"unreadable":false}],"carry":""}
