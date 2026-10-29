PROGRESS: COMPLETE
SKILLS: python

Files: src/exam_engine/utils/text.py (fold), pipeline/router.py (fold in subject_key/known_names), pipeline/parser.py (header check via subject_key), pipeline/examples_check.py (header via router.subject_key; SUBJECT_NAMES removed), config/subjects.json, prompts/dev/subjects/informatics.md, prompts/dev/lang/vi/subjects/informatics.md, examples/FORMAT.md, tests/unit/test_router.py (subject list), tests/unit/test_subjects.py (new).
Tests: unit 245 OK; integration 2 OK; check-prompts --channel dev OK (16 files, 1 variants).
## Defects
None. (parser.py was also changed: it used known_names().casefold(), which rejected "Tin hoc".)
