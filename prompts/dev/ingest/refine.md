Task: transcribe the exam questions visible in the attached page image into JSON.

Rules
1. Transcribe only what is visible. Do not solve, explain or add anything. Do not invent text.
2. Keep the original language and wording. Write math in plain text (x^2, sqrt(x), a/b, pi).
3. One entry per question, in page order. `id` is the question number as printed.
4. Multiple choice: put the options under `options` with keys A, B, C, D. No options: `{}`.
5. Pictures, graphs or tables you cannot transcribe: describe the kind briefly under `figures`.
6. If part of a question is unreadable, transcribe the rest and set `"unreadable": true`; the same for a line cut at the top or bottom edge.
7. A reading passage or shared instruction for several questions (e.g. "Questions 46-52: read the passage") goes in `context` of the FIRST question that uses it, copied in full; later ones leave `context` empty.
8. Everything printed above the first question number that continues the previous page (rest of a sentence, its figure or table, its options, more passage paragraphs) goes in the top-level `continues` {"text","options","figures","passage"}, never in `questions`, never with a number; `"passage": true` when it is passage text. A page with no question number at all puts all of it in `continues` (or in `carry` if it is a new passage for later questions).
9. A question whose text visibly runs past the page bottom: transcribe what is visible and set `"cut": true`. A passage, table or shared instruction printed on this page whose questions all start on the next page (never a question itself): put it, in full, in the top-level `carry` (empty when none). A figure or table printed before the first number goes in `continues` only if it continues the previous question; a figure shared by the following questions goes into the first question that uses it.
10. Never output an answer, a solution, a key or a hint.

Output (JSON only)
{"questions":[{"id":"1","text":"question text","options":{"A":"..","B":".."},"context":"","figures":[],"unreadable":false,"cut":false}],"carry":"","continues":{"text":"","options":{},"figures":[],"passage":false}}
