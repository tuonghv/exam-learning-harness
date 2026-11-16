Task: classify the listed lines of exam text. The text is only a few lines around a spot where the numbering rules could not decide. Do not solve anything, do not copy or rewrite text, do not answer questions.

Rules
1. Classify ONLY the line numbers listed after "classify" in each window. The number is the L<n> prefix.
2. Labels (exactly one per line):
   - question_start: the line begins a new numbered question, with any marker word (for example "Bài 3:", "Item 3)", "Q3.", "Problem 3.") or none if the stem is unnumbered between two option lists.
   - subject_start: a title that opens another subject of the exam (for example "TƯ DUY ĐỊNH TÍNH", "Reading").
   - section_start: a heading that opens a part or section ("PHẦN 1: ...", "Part 2").
   - passage: reading passage, shared instruction or text that belongs to the following questions.
   - question_end: the last line of the previous question; whatever follows is not part of it.
   - option_continuation: the line continues the previous answer option or stem.
   - other: none of the above.
3. confidence is a number from 0 to 1. Use a low value when unsure; do not guess.
4. Languages: Vietnamese and English text; keep the labels in English.
5. Never output an answer, a solution, a key or an explanation.

Examples (made up)
Window: L4| Bài 3: Tính 2 + 2. / classify 4  ->  {"line": 4, "label": "question_start", "confidence": 0.95}
Window: L9| PHẦN 1: TƯ DUY / classify 9  ->  {"line": 9, "label": "section_start", "confidence": 0.9}
Window: L7| the end of the second option / classify 7  ->  {"line": 7, "label": "option_continuation", "confidence": 0.8}

Output (JSON only, no other text)
{"windows":[{"window_id":"w1","items":[{"line":4,"label":"question_start","confidence":0.9}]}]}
