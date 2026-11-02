# Phase 52: human review path (TASK-052; REQ-0055)
Goal: one visible place where the user reviews solved questions and gives feedback the engine can read. Reuse first: result.json (per question id, answer, explanation, solution, uncertainty, verification_status, status_reason, checks), the exam .md (stem and options), refined json (`page`, `needs_review`, markers `[Incomplete: ...]`), report stage helpers (`_one_line`, labels vi/en, answer letter marks), extract_eval Wilson, refcheck reasons. No model call, no schema change.

## Layout (user RAW-00156/00157: few files, user-visible, not work/)
`review/<exam-id>/INDEX.md` (all subjects) and `review/<exam-id>/<subject>.md` (one section per question). `review/` is gitignored (copyright) and created by the command; never under work/.

## Commands (thin, in cli.py COMMANDS like extract-eval)
- `exam.py review-pack --exam-id ID --subject NAME --result RESULT.json --exam EXAM.md [--refined REFINED.json] [--offset N] [--out review]`: writes/overwrites `<subject>.md`, then regenerates `INDEX.md` from every subject file in the folder. `--offset` maps exam position k to the printed number (k+offset), as in the DGNL sections (Vietnamese 0, English 30, Math 60, Science 90); ids in result.json are strings.
- `exam.py review-apply --exam-id ID [--out review]`: reads the `Your review:` lines, prints per subject agreement (agree/disagree/unsure counts, agreement with Wilson 95%), the disagreements by printed number and kind, the doubtful-but-agreed list, and writes `improvements.md` into the same folder (grouped by kind with question numbers; no question text). Never writes into solver inputs, examples or evals/keys.

## Subject file format (stable, parsed by review-apply)
Per question a section: `## Q<printed n>  p.<page>  <status>  answer <A-D or ->  conf <low|medium|high>` then the stem and options as extracted (verbatim from the exam file), `Engine: <short solution, 1-3 lines>`, `Flags: <incomplete|needs_review|quote_fail|declined|none>`, and the last line `Your review: [ ] agree [ ] disagree [ ] unsure | correct: _ | kind: extraction|solution|flawed|other | note: `. Parsing accepts `[x]` on exactly one of the three, a letter A-D or `-` for correct, one kind; anything else is reported as `unparsed` (never guessed).
INDEX.md: one table per exam: subject, n, page, status, answer, conf, flags, review state (blank/agree/disagree/unsure) + totals; instructions at the top (how to review, where to type).

## Tests-first list (tier 0, synthetic result.json/exam .md, never real text in tests)
1. pack: sections count equals result questions; printed numbers = k+offset; answers/flags/pages come from the inputs; missing refined json is fine (page `-`).
2. a declined question (answer null) shows `answer -` and flag declined; an `[Incomplete: missing_text ...]` question shows flag incomplete.
3. INDEX regenerated from two subject files; re-running one subject overwrites only its file.
4. review-apply round trip: fill lines (agree/disagree/unsure, correct, kind, note) -> counts, Wilson, disagreement list; improvements.md has numbers and kinds only.
5. malformed review lines -> `unparsed` list, exit 0, nothing guessed; two boxes ticked -> unparsed.
6. nothing written outside `<out>/<exam-id>/`; refuses `--out` inside examples/, evals/, tests/; `review/` is in .gitignore.
7. idempotence: pack run twice without edits is byte-identical; a pack re-run does NOT overwrite a subject file that already holds user review marks unless `--force-reset` (user input is never lost: re-run merges the marks by printed number, or writes `<subject>.new.md` and says so).
8. real-data smoke (read-only, copyright): build the four DGNL packs from work/dgnl-real/run-*/result.json + e3-*.md + refined3.json with offsets 0/30/60/90 into `review/dgnl-2026-sample/`; counts per subject 30; no file outside review/.
## Plan modes
Reads result and exam files of any plan (single-source solve or pipeline); no change to them.
## Verification
Tier 0 tests + the real-data smoke; tester recomputes counts/answers per question from result.json with its own script and checks the review lines parse; the user then reviews the DGNL pack (first real use).
## Risks / out of scope
Review marks lost on re-run (guarded by test 7); question text only under the gitignored review/; the human key file under evals/keys (only when the user says so, later); the loop skill `review-loop` is written by main in this task.
