# TASK-014 evidence
- `python3 -I -m unittest discover -s tests/unit` -> 323 OK (was 301+12 coder, +10 tester).
- Mutations (tester): find_parts broken -> 9 fail; select_pages range check removed -> 4; parse_pages check removed -> 3; guard in to_exam_text disabled -> 3 (coder). Restored.
- Real PDF input/exam/math/math_12_graduation_2026_001.pdf: ingest-inspect work/ingest-trial/doc.json -> parts exam p1-4, answer_key p5-12, notice printed; `ingest` without --pages -> answer_key_present refusal.
