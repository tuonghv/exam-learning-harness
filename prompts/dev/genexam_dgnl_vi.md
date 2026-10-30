You write ONE new item in the style of the Vietnamese-language part (tiếng Việt) of the Vietnamese
university competency assessment exam (ĐGNL, e.g. ĐHQG-HCM / ĐHQG-HN). Write in Vietnamese. Four
options A-D, exactly one clearly correct, the others plausible slips; the correct answer must be
defensible by a standard rule of Vietnamese (spelling, word formation, grammar, meaning) or by the
text, not by taste.

Reply with ONE JSON object and nothing else:
{"skill": "<topic tag, English>", "question": "<the question or the sentence with a blank ______>",
 "passage": "<2-4 sentence text, ONLY for a reading item, else an empty string>",
 "options": {"A": "...", "B": "...", "C": "...", "D": "..."}, "correct": "A|B|C|D",
 "solution": "<one or two sentences in Vietnamese: why the answer is right>"}

Rules: use exactly the topic given below; new sentences for each seed; the question must not
contain the answer or the explanation.

Difficulty (field "Level" below): "harder" means near-correct distractors that each fail for a
specific reason, a rule with an exception, or a reading item that needs inference across sentences;
exactly one option must still be defensible by a rule or by the text. "hard" or "easy": a plainer item.
