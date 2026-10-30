You write ONE new item in the style of the Vietnamese university competency assessment exam
(ĐGNL, e.g. ĐHQG-HCM / ĐHQG-HN), section "math, logic and data analysis". Vietnamese language,
four options A-D, exactly one correct, all options numbers or fractions, no figure or table.

Reply with ONE JSON object and nothing else:
{"skill": "<topic tag, Vietnamese>", "question": "<the question text>",
 "options": {"A": "...", "B": "...", "C": "...", "D": "..."}, "correct": "A|B|C|D",
 "solution": "<short worked solution, Vietnamese>",
 "check": "<one arithmetic expression whose value equals the correct option, using + - * / ** sqrt()>"}

Rules: a different topic and numbers for each seed (sequences, percent and ratio, probability,
logic puzzles, reading a small data set given in words); wrong options are plausible slips; the
question must not contain the answer or the solution.
