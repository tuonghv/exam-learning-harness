You write ONE new exam question for a Vietnamese Grade 12 high-school graduation exam.
Subject: Mathematics. Write the question in Vietnamese. It must have exactly one numeric or
fraction answer that can be checked by plain arithmetic.

Reply with ONE JSON object and nothing else:
{"skill": "<topic tag, Vietnamese>", "question": "<the question text>",
 "final_answer": "<the final answer only, e.g. 37/42>",
 "solution": "<short worked solution, Vietnamese>",
 "check": "<one arithmetic expression whose value equals final_answer, using + - * / ** sqrt()>"}

Rules: a different topic and different numbers for each seed; no figure or table; the question
must not contain the answer or the solution.

Difficulty (field "Level" below): "hard" means 3-4 solving steps, a common trap (sign, domain,
unit, forgetting to simplify) and a topic other than the simplest formula; "easy" is one step.
