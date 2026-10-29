Task: transcribe the exam questions visible in the attached page image into JSON.

Rules
1. Transcribe only what is visible. Do not solve, explain or add anything. Do not invent text.
2. Keep the original language and wording. Write math in plain text (x^2, sqrt(x), a/b, pi).
3. One entry per question, in page order. `id` is the question number as printed.
4. Multiple choice: put the options under `options` with keys A, B, C, D. No options: `{}`.
5. Pictures, graphs or tables you cannot transcribe: describe the kind briefly under `figures`.
6. If part of a question is unreadable, transcribe the rest and set `"unreadable": true`.
7. Never output an answer, a solution, a key or a hint.

Output (JSON only)
{"questions":[{"id":"1","text":"question text","options":{"A":"..","B":".."},"figures":[],"unreadable":false}]}
