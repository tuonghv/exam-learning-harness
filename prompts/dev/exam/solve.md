Task: solve the exam file below.

Input: the exam file text (format of examples/FORMAT.md: header lines, Instructions, optional
Passage, then `## Question N` blocks) and `Language: vi|en` for your explanations.

Rules
1. Read the whole file first. Solve every question.
2. Explain in the `Language:` value. English items stay in English. Do not translate the question.
   With `Language: vi`, write `solution`, `explanation`, `checks` and `uncertainty.reason` in normal Vietnamese with full diacritics (UTF-8), never unaccented ASCII. English words and terms stay as they are.
3. `answer` by type: multiple choice = one letter A-D; sentence ordering = letters joined with `-`
   (`c-a-d-b-e`); calculation = value, unit and the rounding used (`2.5 m/s^2`); short answer = the exact
   value or phrase; an open (essay/rubric) task = `Open`.
4. `checks` = at least one way to confirm the answer differently (substitute back, unit analysis, limiting
   case, quote). For a calculation also give `expr`: the final numeric expression as plain Python
   arithmetic, so code can recompute it.
5. A `## Group` block is shared context of its questions; `### Sibling answers` is context only, do not re-answer it.
6. If the question asks for an approximate or nearest value ("closest", "approximately", "nearest",
   Vietnamese "gần nhất" / "xấp xỉ"), compute every plausible reading of the wording (for example start or
   end of a period, inclusive or exclusive), then choose the option whose value is nearest to a computed
   reading. Never discard a computed value only because no option equals it exactly. List the readings and
   their distances to the options in `checks`.

Output
{"schema_version":"1.0","questions":[{"id":"1","type":"multiple_choice","answer":"A",
"answer_status":"answered","solution":["step 1","step 2"],"explanation":"why, and why each other option is wrong",
"checks":["check text"],"expr":null,"evidence":["exact quote or null"],"uncertainty":{"level":"low","reason":""},
"reasoning_status":"not_independently_verified","issues":[]}],"input_issues":[]}

`answer_status` is answered | uncertain | unanswerable.
