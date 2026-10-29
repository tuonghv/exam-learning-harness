Task: solve the exam file below.

Input: the exam file text (format of examples/FORMAT.md: header lines, Instructions, optional
Passage, then `## Question N` blocks) and `Language: vi|en` for your explanations.

Rules
1. Read the whole file first. Solve every question.
2. Explain in the `Language:` value. English items stay in English. Do not translate the question.
3. `answer` by type: multiple choice = one letter A-D; sentence ordering = letters joined with `-`
   (`c-a-d-b-e`); calculation = value, unit and the rounding used (`2.5 m/s^2`); short answer = the exact
   value or phrase; Literature or other open task = `Open`.
4. `checks` = at least one way to confirm the answer differently (substitute back, unit analysis, limiting
   case, quote). For a calculation also give `expr`: the final numeric expression as plain Python
   arithmetic, so code can recompute it.

Output
{"schema_version":"1.0","questions":[{"id":"1","type":"multiple_choice","answer":"A",
"answer_status":"answered","solution":["step 1","step 2"],"explanation":"why, and why each other option is wrong",
"checks":["check text"],"expr":null,"evidence":["exact quote or null"],"uncertainty":{"level":"low","reason":""},
"reasoning_status":"not_independently_verified","issues":[]}],"input_issues":[]}

`answer_status` is answered | uncertain | unanswerable.
