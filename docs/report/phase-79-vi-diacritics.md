# Report phase 79: Vietnamese diacritics in solve output (TASK-079; REQ-0087)

Verdict: done and verified. Vietnamese explanations now come back with full diacritics; an unaccented reply is flagged and retried.

## What changed
- Both `solve.md` prompts (en and vi) state the rule: with `Language: vi`, `solution`, `explanation`, `checks` and `uncertainty.reason` are written in normal Vietnamese with full diacritics; English terms stay.
- `verifier._diacritics`: for `Language: vi`, a reply with at least 4 unaccented Vietnamese stopwords and no accented letter gets a `diacritics` fail, which uses the existing retry loop. `en` and accented replies pass. Helper `text.has_accents`; schema kind `diacritics`.
- Open questions get the check only when it fails (format + quote rule kept).

## Measured
- Unit: 7 new tests (check cases, prompt rule, retry from unaccented to accented) plus the nearest-value guard with updated prompt hashes: 13 OK.
- Real re-solve of dhqg2024 English (`Language: vi`, $0.21, 4 calls): unaccented-vi explanations 11/20 before, 0/20 after; accented 5 -> 20. Evidence: `docs/report/evidence/TASK-079/` summary of `work/TASK-079/evidence/resolve-english.txt`.

## Limits
- The unaccented test is a stopword heuristic; a mixed reply with a few accents passes.
- Full unit suite keeps 4 failures not caused by this task (examples/dgnl pairing x3, docx text-box x1).
- Other dhqg2024 subjects were not re-solved.
