PROGRESS: COMPLETE
SKILLS: coding, token-efficiency, python, unit-test
# TASK-015 code (REQ-0018, Titan)
Files: src/exam_engine/ingest/adapters/docx.py (new), adapters/__init__.py (register .docx), tests/unit/test_ingest_docx.py (13 tests), tests/unit/test_ingest_spec.py (10 tests, one per spec s.8 case), docs/guide/ingest-usage.md (new), docs/guide/ingest-setup.md (link).
Tests: `python3 -I -m unittest discover -s tests/unit` -> 347 OK (324 + 23). PDF/DOCX tests skip with reason if fitz/docx absent; OCR case skips without tesseract eng.
Mutation: docx.py heading level `int(m.group(1))` -> `1`: test_headings_paragraph_list_valid_and_hash FAILS; restored, green.
Notes/deviations:
- List block type is `list` (schema BLOCK_TYPES has no `list_item`).
- python-docx is installed in user site only; found via optional.load under -I.
- Tables: `rows` kept on the block (as pdf.py), text rows joined "\n", cells " | ".
- Images inside tables are not extracted (unsupported_content). Images in paragraphs follow the paragraph text.
- OLE header -> `encrypted` (also an old .doc; documented).
- toolkit-reference.md has no ingest rows, not touched.
## Defects
None found.
