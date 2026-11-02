# Report phase 54: clean four-level exam format (TASK-054; REQ-0057)

Verdict: adopted. Exam text now has four labelled levels: `## Section:` (subject/part, once per section), `### Instruction for this group` (guide, kept in every question of its group), `## Question N` (header), `### Passage` / `### Question text` + options (real question). `examples/FORMAT.md` documents it; ingest emits it (`split_heading`, `question_lines`), the parser reads it (`section`, `instruction`, `passage`, `stem`; `text` unchanged), `router.heading_subject` maps headings to subjects (diacritic-insensitive; unknown or mismatching -> `WARN:` lines), and `render_questions` renders the labelled blocks. Unlabelled files behave byte-identically.

## Evidence (work/TASK-054/evidence)
- Suite 865 run; only the 4 failures also present at baseline 083d0e4 (lxml, examples/dgnl unknown subject dir x3): baseline-failures.txt vs head-failures.txt identical.
- Golden: parse dict and solve_prompt of 25 unlabelled inputs equal baseline; DGNL re-emit from refined3.json: 30 questions per subject, option dicts equal to old e3-*.md; English 31-35 prompt has the instruction 5x and `1.2. TIẾNG ANH` once (golden.txt).
- Security pass clean; minor quadratic regex noted (D1 in verify.md).

## Limits
No paid re-solve of English q1-5: "answers unchanged" rests on prompt structure plus golden. A context with a passage but no guide line keeps the old unlabelled form. DGNL golden skips when work/ is absent.

Follow-up: REQ-0058 (group-aware solving: independent / passage / dependent) builds on these levels.
User instructions honoured: RAW-00162.

Evidence files for crosscheck: docs/report/evidence/TASK-054/ (index: docs/report/INDEX.md).
