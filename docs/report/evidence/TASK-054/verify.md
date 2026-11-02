PROGRESS: COMPLETE
SKILLS: verify, crosscheck, token-efficiency

Tier 1 (content/unit), no AI run. Evidence: work/TASK-054/evidence/suite.txt (rc 1), golden.txt (rc 0).

## Verdicts
- AC0 format (4 levels, FORMAT.md, parser, labelled prompt): VERIFIED (static + unit). parser.py:16,60-86 reads `## Section:` and `### Instruction for this group|Passage|Question text`; solver.py:63-66 renders labelled blocks. Ingest/refine emission verified via golden DGNL re-emit (golden.txt rc0, 3 tests; test.md:7). FORMAT.md edit not re-read by me: UNVERIFIED.
- AC1 instruction kept in every group question: VERIFIED by tests/unit/test_clean_levels.py (cloze family, per test.md) and solver.py:63-66; suite shows no failure there.
- AC2 heading out of stem, once per section: VERIFIED (solver.py:60-62 emits `## Section:` once per change; stem separate). "Answers unchanged": UNVERIFIED by real solve (paid re-solve of English q1-5 not run); only prompt-structure + golden sha equal base 2461f4f vs HEAD for 25 unlabelled files (test.md:5).
- AC3 DGNL regression: VERIFIED (golden.txt: 30 q/subject, option dicts equal old e3-*.md; skips if work/ absent, so not CI-reproducible).
- AC4 heading -> subject: VERIFIED for alias/diacritic mapping (router.py:25-36, test_clean_levels.py:154; segment.py:43-51 uses it). Unknown-heading warning + Haiku fallback gating: not seen in grep of parser.py (no `warn` hit shown beyond limit); UNVERIFIED, coder claims warnings in 54.6 (commit 6b9b996).
- AC5 `Instruction for this group:` labelled block, once per question: VERIFIED (solver.py:63-66; golden unlabelled unchanged).

## Suite
- suite.txt: 865 run, failures=3 errors=1 (rc 1). Failures: lxml missing (env), `examples/dgnl: pairing: unknown subject dir` x3 (test_check_examples 12b, test_req0012 cwd, test_scripts_exam). Claimed pre-existing (code.md:13) but not proven against baseline: UNVERIFIED. NEXT: run same 3 tests at 083d0e4/2461f4f via save-evidence to confirm they fail there too.

## Security pass
- Grep of eval/exec/subprocess/os.system in changed ingest/parser/router/segment: none. No new AI call (heading_subject is rule-based; no claude/subprocess in changed files).
- Regexes: router.py:25-26 anchored, bounded; parser.py:13-16,65-86 line-anchored, no nested quantifiers. Minor: `\s+#.*$` (parser.py:34) and `(.*?)\s*$` (parser.py:15) are O(n^2) on very long whitespace runs; no catastrophic backtracking. Low.
- Untrusted text only parsed to dicts and rendered into a prompt (prompt-injection surface unchanged).

## Defects
- D1 minor: parser.py:15,34 quadratic on huge whitespace lines (DoS only, low).

## Gaps
- Paid re-solve of English q1-5 not run: answer equality only by prompt structure.
- AC4 unknown-heading warning, FORMAT.md content, 4 suite failures vs baseline: need evidence (see above).
- AC checkboxes unticked in REQ-0057 (main to tick).
